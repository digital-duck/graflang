// release.cedar: a file may be published only when a person approved it.
permit (
    principal == Service::"release-approval",
    action == Action::"publish",
    resource
) when { context.human_approval == true };
