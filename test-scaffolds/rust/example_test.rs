// Rust test scaffold — tests live in an inline #[cfg(test)] module at the end
// of the source file. Do NOT create a separate _test.rs sibling file.
// Replace my_function and placeholder values with real names.

pub fn my_function(input: &str) -> Result<String, String> {
    if input.is_empty() {
        return Err("input must not be empty".to_string());
    }
    Ok(format!("processed_{}", input))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn returns_processed_string_for_valid_input() {
        let result = my_function("hello").unwrap();
        assert_eq!(result, "processed_hello");
    }

    #[test]
    fn returns_error_for_empty_input() {
        let err = my_function("").unwrap_err();
        assert!(err.contains("must not be empty"), "unexpected error: {err}");
    }

    // Requires tokio in Cargo.toml: tokio = { version = "1", features = ["rt"] }
    #[tokio::test]
    async fn async_variant_resolves_correctly() {
        // Replace with a real async function.
        let result = async { my_function("async_input") }.await.unwrap();
        assert_eq!(result, "processed_async_input");
    }
}
