// digest.cedar: may the notes_digest workflow read its notes and write its digest?
//
// The guard asks Cedar for Action::"digest" and Cedar denies by default. The one permit below lets this workflow
// (and no other service) do it. Remove it, or add a `forbid`, and nothing is read or written: the QUERY and the EMIT
// sit behind the guard's `allow` port, and `graf validate` refuses a graph where they do not.

permit (
    principal == Service::"notes-digest",
    action == Action::"digest",
    resource
);
