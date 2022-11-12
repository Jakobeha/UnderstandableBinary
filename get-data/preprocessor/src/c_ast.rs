use std::fs::File;
use std::io::BufReader;
use std::path::Path;
use serde::Deserialize;

pub type Node = clang_ast::Node<Data>;

#[derive(Deserialize)]
pub enum Data {
    FunctionDecl {
        name: Option<String>,
        loc: clang_ast::SourceLocation,
        range: clang_ast::SourceRange
    },
    Other,
}

pub fn read_from_path(path: &Path) -> std::io::Result<Node> {
    let file = File::open(path)?;
    // Always buffer when deserializing unbuffered streams for efficiency
    let reader = BufReader::new(file);
    let node = serde_json::from_reader(reader)?;
    Ok(node)
}

pub struct DoRecurse(pub bool);

pub fn visit(node: &Node, mut f: impl FnMut(&Node) -> DoRecurse) {
    _visit(node, &mut f);
}

fn _visit(node: &Node, f: &mut dyn FnMut(&Node) -> DoRecurse) {
    let do_recurse = f(&node);
    if do_recurse.0 {
        for child in &node.inner {
            _visit(child, f);
        }
    }
}