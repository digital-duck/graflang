// release_policy.cedar: when may the compliance_audit workflow release a document?
//
// The release_guard node asks Cedar for Action::"release_document" and supplies the context
//   compliant    true when the rule check passed on the document being released
//   is_external  true when the destination is outside the organisation
//
// Cedar denies by default: a document is released only if a `permit` applies. There is no catch-all
// `forbid`, because forbid overrides permit and would block every release.

permit (
    principal == Service::"compliance-workflow",
    action == Action::"release_document",
    resource
)
when { context.compliant == true };

// Defence in depth: an external release of a document that is not compliant is refused outright,
// whatever other permit rules are added to this file later.
forbid (
    principal,
    action == Action::"release_document",
    resource
)
when { context.is_external == true && context.compliant != true };
