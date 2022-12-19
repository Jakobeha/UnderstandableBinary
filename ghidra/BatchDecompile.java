//Batch decompile all files in a directory
//@author jakobeha
//@category Decompiler
//@keybinding 
//@menupath 
//@toolbar 

import java.io.IOException;
import java.nio.file.*;
import java.util.List;
import java.util.Objects;
import java.util.stream.Collectors;

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
        var importExistingFiles = this.getScriptArgs().length > 2 ?
                Boolean.parseBoolean(this.getScriptArgs()[2]) :
                this.askYesNo("Import existing files", "OK");
        var analyzeExistingFiles = this.getScriptArgs().length > 2 ?
                Boolean.parseBoolean(this.getScriptArgs()[2]) :
                this.askYesNo("Analyze existing files", "OK");
        var project = state.getProject();
        this.batchDecompile(project, srcDir, importExistingFiles, analyzeExistingFiles);
    }

    public void batchDecompile(
            Project project,
            Path projectDir,
            boolean importExistingFiles,
            boolean analyzeExistingFiles
    ) throws Exception {
        // We can't decompile while searching (streaming) because it Files.find is kind of broken
        this.logInfo( "*** IMPORTING FILES IN " + projectDir + "...");
        List<ImportedPath> importedPaths;
        try (var pathStream = Files.find(
                projectDir,
                Integer.MAX_VALUE,
                (binaryPath, fileAttr) -> fileAttr.isRegularFile() && binaryPath.getFileName().toString().endsWith(".o")
        )) {
            importedPaths = pathStream.map(binaryPath -> {
                try {
                    this.monitor.clearCanceled();
                    return this.importPath(binaryPath, project, importExistingFiles);
                } catch (Exception e) {
                    this.logError("Error importing " + binaryPath, e, true);
                    return null;
                }
            }).filter(Objects::nonNull).collect(Collectors.toList());
        }

        if (importedPaths.isEmpty()) {
            this.logInfo("No files found (*** BATCH DECOMPILE DONE)");
        }

        var decompiler = new FlatDecompilerAPI(this);
        this.logInfo( "*** DECOMPILING " + importedPaths.size() + " FILES");
        for (var importedPath : importedPaths) {
            var binaryPath = importedPath.binaryPath;
            var programs = importedPath.programs;
            var disassembledPath = getDisassembledPath(binaryPath);
            try {
                this.monitor.clearCanceled();
                this.decompile(binaryPath, programs, disassembledPath, analyzeExistingFiles, decompiler);
            } catch (Exception e) {
                this.logError("Error decompiling " + binaryPath, e, true);
            }
        }
    }

    private ImportedPath importPath(
            Path binaryPath,
            Project project,
            boolean importExistingFiles
    ) throws Exception {
        if (!importExistingFiles) {
            var programFile = getSerialDomainFile(binaryPath, project);
            if (programFile != null) {
                this.logInfo("Loading serialized imported " + binaryPath);
                var program = (Program) programFile.getDomainObject(this, false, false, monitor);
                return new ImportedPath(binaryPath, List.of(program));
            }
        }

        this.logInfo( "IMPORTING " + binaryPath + "...");
        var createSerialDomainFile = this.createSerialDomainFile(binaryPath, project);
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
            createSerialDomainFile.parent.createFile(createSerialDomainFile.name, program, monitor);
        } else {
            this.logWarn(programs.size() + " programs found at one location: " + binaryPath);
        }
        return new ImportedPath(binaryPath, programs);
    }

    private void decompile(Path binaryPath, List<Program> programs, Path disassembledPath, boolean analyzeExistingFiles, FlatDecompilerAPI decompiler) throws Exception {
        if (!analyzeExistingFiles && Files.exists(disassembledPath)) {
            this.logInfo("Skipping " + binaryPath + " (already decompiled)");
            return;
        }

        // Create empty file so that if we fail, we don't retry when we-running disassemble without processExistingFiles
        Files.deleteIfExists(disassembledPath);
        Files.createFile(disassembledPath);

        this.logInfo( "ANALYZING " + binaryPath + "...");
        for (var program : programs) {
            var transaction = program.startTransaction("BatchDecompile analyze");
            try {
                // Analysis takes a lot of memory
                System.gc();
                this.analyzeChanges(program);
                program.endTransaction(transaction, true);

                // Save analysis
                if (programs.size() == 1) {
                    program.save("Analyzed", monitor);
                }
            } catch (OutOfMemoryError error) {
                System.gc();
                program.endTransaction(transaction, false);
                throw new Exception("Out of memory while analyzing " + binaryPath, error);
            }
        }

        this.logInfo( "DECOMPILING " + binaryPath + "...");
        for (var program : programs) {
            var firstLog = true;
            for (var func : program.getFunctionManager().getFunctions(true)) {
                if (!func.isExternal()) {
                    this.logInfo("Decompiling " + binaryPath.getFileName() + " function " + func.getName() + "...");
                    try {
                        var disassembled = decompiler.decompile(func);
                        if (disassembled.contains("Truncating control flow here")) {
                            this.logError("Warning decompiling " + binaryPath.getFileName() + " function " + func.getName());
                        } else {
                            Files.writeString(disassembledPath, "// FUNCTION " + func.getName(), StandardOpenOption.APPEND);
                            Files.writeString(disassembledPath, disassembled, StandardOpenOption.APPEND);
                        }
                    } catch (Exception e) {
                        // I have no idea how to check these functions
                        this.logError("Error decompiling " + binaryPath.getFileName() + " function " + func.getName(), e, firstLog);
                        firstLog = false;
                    }
                }
            }

            program.release(this);
        }
    }

    // project.getProjectLocator().getProjectDir() = a path to inside of the ghidra.rep folder
    // .relative(binaryPath) = ../<relative path> (because we go out of the ghidra.rep folder and then to the path)
    // We want to return the relative path *inside* of the ghidra.rep folder,
    // so that ghidra.rep has an "equivalent file system hierarchy" where each object file corresponds to ghidra program data
    private String _getRelativeSerialPath(Path binaryPath, Project project) {
        var binaryPathWithDifferentExtension = binaryPath.getParent().resolve(binaryPath.getFileName().toString() + ".ghidra");
        var path = getProjectPath(project).relativize(binaryPathWithDifferentExtension).toString();
        assert path.startsWith("../");
        return "filetree" + path.substring(2);
    }

    private DomainFile getSerialDomainFile(Path binaryPath, Project project) {
        // Ghidra requires the path to start with "/" even though it's actually relative
        return project.getProjectData().getFile("/" + _getRelativeSerialPath(binaryPath, project));
    }

    private CreateSerialDomainFile createSerialDomainFile(Path binaryPath, Project project) throws IOException, InvalidNameException {
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
        return new CreateSerialDomainFile(parent, name);
    }

    private Path getSerialPath(Path binaryPath, Project project) {
        return getProjectPath(project).resolve(this._getRelativeSerialPath(binaryPath, project));
    }

    private Path getProjectPath(Project project) {
        return project.getProjectLocator().getProjectDir().toPath().normalize();
    }

    private Path getDisassembledPath(Path binaryPath) {
        return binaryPath.getParent().resolve(binaryPath.getFileName().toString() + ".c");
    }

    private void logInfo(String msg) {
        println(msg);
    }

    private void logWarn(String msg) {
        printerr("WARNING: " + msg);
    }

    private void logError(String msg) {
        printerr(msg);
    }

    private void logError(String msg, Exception error, boolean logFull) {
        printerr(msg + "\n" + error.getMessage());

        if (logFull) {
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

    private record CreateSerialDomainFile(DomainFolder parent, String name) {}
}
