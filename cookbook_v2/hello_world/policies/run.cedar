// run.cedar: which languages may the generated program be run in? Anything else is shown, not run.
permit (
    principal == Service::"hello-world",
    action == Action::"run_program",
    resource
) when { ["python", "py", "python3", "javascript", "js", "node"].contains(context.language) };
