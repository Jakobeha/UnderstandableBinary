/// Adapts [std::io::Write] to [std::fmt::Write].
pub struct IoWrite2FmtWrite<'a, W: std::io::Write>(&'a mut W);

/// Adapts [std::io::Write] to [std::fmt::Write]. Additionally, always succeeds, but will stop
/// writing and set `result` field if an I/O error is encountered
pub struct IoWrite2FmtWriteCatch<'a, W: std::io::Write> {
    inner: &'a mut W,
    result: std::io::Result<()>
}

impl<'a, W: std::io::Write> IoWrite2FmtWrite<'a, W> {
    pub fn new(inner: &'a mut W) -> Self {
        Self(inner)
    }
}

impl<'a, W: std::io::Write> IoWrite2FmtWriteCatch<'a, W> {
    pub fn new(inner: &'a mut W) -> Self {
        Self {
            inner,
            result: Ok(())
        }
    }

    pub fn into_result(self) -> std::io::Result<()> {
        self.result
    }
}

impl<'a, W: std::io::Write> std::fmt::Write for IoWrite2FmtWrite<'a, W> {
    fn write_str(&mut self, s: &str) -> std::fmt::Result {
        std::io::Write::write_all(&mut self.0, s.as_bytes()).map_err(|_| std::fmt::Error)
    }
}

impl<'a, W: std::io::Write> std::fmt::Write for IoWrite2FmtWriteCatch<'a, W> {
    fn write_str(&mut self, s: &str) -> std::fmt::Result {
        if let Ok(()) = self.result {
            if let Err(error) = std::io::Write::write_all(&mut self.inner, s.as_bytes()) {
                self.result = Err(error);
            }
        }
        Ok(())
    }
}