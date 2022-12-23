//Batch decompile all files in a directory
//@author jakobeha
//@category Decompiler
//@keybinding 
//@menupath 
//@toolbar 

import java.io.IOException;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.nio.file.*;
import java.util.List;
import java.util.Objects;
import java.util.concurrent.atomic.AtomicInteger;

import ghidra.app.decompiler.flatapi.FlatDecompilerAPI;
import ghidra.app.script.GhidraScript;
import ghidra.app.services.ConsoleService;
import ghidra.app.util.importer.*;
import ghidra.app.util.opinion.LoaderService;
import ghidra.framework.model.DomainFile;
import ghidra.framework.model.DomainFolder;
import ghidra.framework.model.Project;
import ghidra.program.model.listing.Program;
import ghidra.util.InvalidNameException;
import ghidra.util.Msg;

@SuppressWarnings("unused")
public class BatchDecompile extends GhidraScript {
    public void run() throws Exception {
        var srcDir = this.getScriptArgs().length > 0 ?
                Path.of(this.getScriptArgs()[0]).normalize() :
                this.askDirectory("Data (sources) root", "OK").toPath();
        var importExistingFiles = this.getScriptArgs().length > 1 ?
                Boolean.parseBoolean(this.getScriptArgs()[1]) :
                this.askYesNo("Import existing files", "OK");
        var decompileExistingFiles = this.getScriptArgs().length > 2 ?
                Boolean.parseBoolean(this.getScriptArgs()[2]) :
                this.askYesNo("Decompile existing files", "OK");
        var statsDir = this.getScriptArgs().length > 3 ?
                this.getScriptArgs()[3] :
                this.askString("Stats dir for watch mode (empty otherwise)", "OK", "");
        var project = state.getProject();
        this.batchDecompile(project, srcDir, importExistingFiles, decompileExistingFiles, statsDir);
    }

    public void batchDecompile(
            Project project,
            Path projectDir,
            boolean importExistingFiles,
            boolean decompileExistingFiles,
            String statsDir
    ) throws Exception {
        // TODO: Watch mode, also refactor so that it decompiles vcpkg artifacts and handles apt artifact nesting properly
        // We can't decompile while searching (streaming) because it Files.find is kind of broken
        this.logInfo( "*** SEARCHING FILES IN %s...", projectDir);
        List<Path> paths;
        try (var pathStream = Files.find(
                projectDir,
                Integer.MAX_VALUE,
                (binaryPath, fileAttr) -> fileAttr.isRegularFile() && binaryPath.getFileName().toString().endsWith(".o")
        )) {
            paths = pathStream.toList();
        }

        int numToImport;
        if (importExistingFiles) {
            numToImport = paths.size();
            this.logInfo( "*** IMPORTING %d FILES", numToImport);
        } else {
            var numToSkip = (int)paths.stream().filter(binaryPath ->
                    getSerialDomainFile(binaryPath, project) != null
            ).count();
            numToImport = paths.size() - numToSkip;
            this.logInfo("*** IMPORTING %d NEW FILES ( + SKIPPING %d)", numToImport, numToSkip);
        }
        var numImported = new AtomicInteger(0);
        var importedPaths = paths.stream().map(binaryPath -> {
            try {
                return this.importPath(binaryPath, project, importExistingFiles, numToImport, numImported);
            } catch (Exception e) {
                this.logError("Error importing " + binaryPath, e);
                return null;
            }
        }).filter(Objects::nonNull).toList();

        int numToDecompile;
        if (decompileExistingFiles) {
            numToDecompile = importedPaths.size();
            this.logInfo( "*** DECOMPILING %d FILES", numToDecompile);
        } else {
            var numToSkip = (int)importedPaths.stream().filter(importedPath ->
                    Files.exists(getDisassembledPath(importedPath.binaryPath))
            ).count();
            numToDecompile = importedPaths.size();
            this.logInfo("*** DECOMPILING %d NEW FILES ( + SKIPPING %d)", numToDecompile, numToSkip);
        }
        var numDecompiled = new AtomicInteger(0);
        for (var importedPath : importedPaths) {
            var binaryPath = importedPath.binaryPath;
            var programs = importedPath.programs;
            var disassembledPath = getDisassembledPath(binaryPath);
            try {
                this.decompile(binaryPath, programs, disassembledPath, decompileExistingFiles, numToDecompile, numDecompiled);
            } catch (Exception e) {
                this.logError("Error decompiling " + binaryPath, e);
            }
        }
    }

    private ImportedPath importPath(
            Path binaryPath,
            Project project,
            boolean importExistingFiles,
            int numToImport,
            AtomicInteger numImported
    ) throws Exception {
        if (!importExistingFiles) {
            var programFile = getSerialDomainFile(binaryPath, project);
            if (programFile != null) {
                this.logInfo("Loading serialized imported %s", binaryPath);
                var program = (Program) programFile.getDomainObject(this, false, false, monitor);
                return new ImportedPath(binaryPath, List.of(program));
            }
        }
        var progress = (float)numImported.get() / (float)numToImport * 100f;
        var index = numImported.incrementAndGet();

        this.logInfo( "** IMPORTING %s... (%d/%d aka %.02f%% of phase 1/2)", binaryPath, index, numToImport, progress);
        numImported.incrementAndGet();
        var createSerialDomainFile = this.prepareCreateSerialDomainFile(binaryPath, project);
        var programs = AutoImporter.importFresh(
                binaryPath.toFile(),
                createSerialDomainFile.parent,
                this,
                new MessageLog(),
                monitor,
                LoaderService.ACCEPT_ALL, LoadSpecChooser.CHOOSE_THE_FIRST_PREFERRED, null,
                OptionChooser.DEFAULT_OPTIONS, MultipleProgramsStrategy.ALL_PROGRAMS);
        if (programs.size() == 1) {
            var program = programs.get(0);
            var existingFile = createSerialDomainFile.parent.getFile(createSerialDomainFile.name);
            if (existingFile != null) {
                existingFile.delete();
            }
            createSerialDomainFile.parent.createFile(createSerialDomainFile.name, program, monitor);
        } else {
            this.logWarn("%d programs found at one location: %s (we can't cache these because multiple programs is only partially supported)", programs.size(), binaryPath);
        }
        return new ImportedPath(binaryPath, programs);
    }

    private void decompile(
            Path binaryPath,
            List<Program> programs,
            Path disassembledPath,
            boolean decompileExistingFiles,
            int numToDecompile,
            AtomicInteger numDecompiled
    ) throws Exception {
        if (!decompileExistingFiles && Files.exists(disassembledPath)) {
            this.logInfo("Skipping %s (already decompiled)", binaryPath);
            return;
        }
        var progress = (float)numDecompiled.get() / (float)numToDecompile * 100f;
        var index = numDecompiled.incrementAndGet();

        // Create empty file so that if we fail, we don't retry when we-running disassemble without processExistingFiles
        Files.deleteIfExists(disassembledPath);
        Files.createFile(disassembledPath);

        this.logInfo("** ANALYZING %s... (%d/%d aka %.02f%% of phase 2/2)", binaryPath, index, numToDecompile, progress);
        for (var program : programs) {
            var transaction = program.startTransaction("BatchDecompile analyze");
            try {
                // Analysis takes a lot of memory
                System.gc();
                this.analyzeAll(program);
                program.endTransaction(transaction, true);

                // Save analysis
                if (programs.size() == 1) {
                    program.save("Analyzed", monitor);
                }
            } catch (Throwable exception) {
                program.endTransaction(transaction, false);
                throw exception;
            }
        }

        this.logInfo( "** DECOMPILING %s... (%d.5/%d aka %.02f%% of phase 2/2)", binaryPath, index, numToDecompile, progress + (0.5f / (float)numToDecompile * 100f));
        for (var program : programs) {
            var firstLog = true;
            currentProgram = program;
            var decompiler = new FlatDecompilerAPI(this);
            try {
                for (var func : program.getFunctionManager().getFunctions(true)) {
                    if (!func.isExternal()) {
                        try {
                            var disassembled = decompiler.decompile(func);
                            if (disassembled.contains("Truncating control flow here")) {
                                this.logWarn("Bad decompile: " + binaryPath.getFileName() + " function " + func.getName());
                            } else {
                                Files.writeString(disassembledPath, "// FUNCTION " + func.getName(), StandardOpenOption.APPEND);
                                Files.writeString(disassembledPath, disassembled, StandardOpenOption.APPEND);
                            }
                        } catch (Exception e) {
                            if (firstLog) {
                                // I have no idea how to check these functions
                                this.logError("Error decompiling " + binaryPath.getFileName() + " function " + func.getName(), e);
                                firstLog = false;
                            }
                        }
                    }
                }
            } finally {
                decompiler.dispose();
                program.release(this);
            }
        }
    }

    // project.getProjectLocator().getProjectDir() = a path to inside of the ghidra.rep folder
    // .relative(binaryPath) = ../<relative path> (because we go out of the ghidra.rep folder and then to the path)
    // We want to return the relative path *inside* of the ghidra.rep folder,
    // so that ghidra.rep has an "equivalent file system hierarchy" where each object file corresponds to ghidra program data
    private String _getRelativeSerialPath(Path binaryPath, Project project) {
        var binaryPathWithDifferentExtension = binaryPath.getParent().resolve(binaryPath.getFileName().toString() + ".ghidra").toAbsolutePath().normalize();
        var path = getProjectPath(project).relativize(binaryPathWithDifferentExtension).toString();
        assert path.startsWith("../");
        return "filetree" + path.substring(2);
    }

    private DomainFile getSerialDomainFile(Path binaryPath, Project project) {
        // Ghidra requires the path to start with "/" even though it's actually relative
        return project.getProjectData().getFile("/" + _getRelativeSerialPath(binaryPath, project));
    }

    /** Create serial domain file's parent if not exists, and get its parent and name */
    private CreatingSerialDomainFile prepareCreateSerialDomainFile(Path binaryPath, Project project) throws IOException, InvalidNameException {
        var relativeSerialPathComponents = this._getRelativeSerialPath(binaryPath, project).split("/");
        var parent = project.getProjectData().getRootFolder();
        for (var i = 0; i < relativeSerialPathComponents.length - 1; i++) {
            var component = relativeSerialPathComponents[i];
            var child = parent.getFolder(component);
            if (child == null) {
                child = parent.createFolder(component);
            }
            parent = child;
        }
        var name = relativeSerialPathComponents[relativeSerialPathComponents.length - 1];
        return new CreatingSerialDomainFile(parent, name);
    }

    private Path getProjectPath(Project project) {
        return project.getProjectLocator().getProjectDir().toPath().toAbsolutePath().normalize();
    }

    private Path getDisassembledPath(Path binaryPath) {
        return binaryPath.getParent().resolve(binaryPath.getFileName().toString() + ".c");
    }

    private void logInfo(String msg, Object... args) {
        println(String.format(msg, args));
    }

    private void logWarn(String msg, Object... args) {
        printerr(String.format("WARNING: " + msg, args));
    }

    private void logError(String msg) {
        printerr(msg);
    }

    private void logError(String msg, Exception error) {
        printerr(msg + "\n" + error.getMessage());

        if (isRunningHeadless()) {
            var stackTrace = new StringWriter();
            error.printStackTrace(new PrintWriter(stackTrace));
            printerr("Stack trace: " + stackTrace);
        } else {
            try {
                var tool = state.getTool();
                var console = tool.getService(ConsoleService.class);
                console.addException(getScriptName(), error);
            } catch (Exception e) {
                Msg.error(this, "Exception", error);
            }
        }
    }

    private record ImportedPath(Path binaryPath, List<Program> programs) {}

    private record CreatingSerialDomainFile(DomainFolder parent, String name) {}
}
