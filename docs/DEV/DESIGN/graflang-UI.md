# GraphLang UI: review of the Streamlit app (`graf vis --edit`)

Date: 2026-11-01. Scope: `graphlang/grafv/app.py`, `ui.py`, `chat_ops.py`, `attachments.py`, `editor.py`, `pages/*.py`, and the pieces they use. The review was done by reading the code; three of the bugs were confirmed by a small check, the rest by reading. Nothing was verified in a real browser (the Ace editor, the iframe and Cytoscape are untested by `AppTest`).

Status: everything listed here is fixed, each with a regression test, except what the last section says is not covered.

## Bugs

| # | Finding | Status |
|---|---|---|
| 1 | Invalid YAML typed in a config box (Node tab, New config key, Add node) crashed the page: ruamel's `ParserError` is neither `EditError` nor `ValueError`, so `attempt()` did not catch it. `parse_value` now turns a `YAMLError` into `EditError("that is not valid YAML: ...")`. | fixed: `test_invalid_yaml_typed_in_a_box_is_an_edit_error_not_a_parser_crash`, `test_a_yaml_typo_in_the_add_node_form_shows_an_error_and_keeps_the_page` |
| 2 | "Open in the Edit page" on Create set `target` but not `opened`; Edit shows "Open a recipe" when `opened` is unset. It now calls `ui.open_graph`. | fixed: `test_open_in_edit_after_saving_shows_the_saved_app_even_if_edit_was_never_opened` |
| 3 | The Run tab ran a real model with no call cap (`MeteredLLM` without `max_calls`; only `max_steps=200` bounded it). `GraphEditor.run(max_calls=)` and a "Most model calls" box (default 10, shown only for a real model) now cap it; a run that would exceed it fails with `LimitExceeded`. | fixed: `test_a_real_model_run_is_capped_in_calls`, `test_the_mock_run_has_no_cap_box` |
| 4 | In the Edges tab the Type radio was inside `st.form`, so From/To lists did not follow it until submit. The radio is outside the form now. | fixed: `test_the_edge_lists_follow_the_type_at_once` |
| 5 | A Create draft could be saved once: `write_app(force=False)` refused the folder the draft had just written. A draft may now replace its own folder (the button says "Save again, replacing NAME/", and its help says files changed on the Edit page are overwritten); a different draft with a taken name is still refused. Files that an earlier revision wrote and a later one dropped stay on disk. | fixed: `test_a_draft_can_be_saved_again_after_a_revision_and_undo_takes_its_spec_back`, `test_create_saves_into_apps_and_refuses_to_overwrite` |
| 6 | Undo on Create did not roll back `draft["spec"]`, so an undone "Change: ..." still reached `create.json`. An undo step is now `(files, spec)`. | fixed (same test as 5) |
| 7 | Settings: "Remove the saved KEY" saved the whole form (unsaved provider/model/height edits included), and changing the provider kept the old model text (a keyed widget ignores `value` after its first run). Remove now saves only the key change; the model box is keyed by provider. | fixed: `test_removing_a_saved_key_does_not_save_the_other_unsaved_edits`, `test_changing_the_provider_does_not_carry_the_old_model_name_over` |
| 8 | Create with an empty or invalid name sent the message, failed in `check_name`, and the typed text was lost. The name is checked first; the chat keeps the message and says to name the app, nothing is sent to the model. | fixed: `test_create_asks_for_a_name_before_calling_the_model` |

## Gaps

- **Unsaved edits were dropped silently** by Browse files > Open, the Browse page's Open, Reload from disk, "Copy to my apps", "Make an editable long-form copy" and Create's "Open in the Edit page". Those buttons are now off while the Edit page holds unsaved changes (`ui.unsaved()`: graph edits or staged prompt files), with a line saying why, like Clone. Status: fixed; tests `test_opening_or_reloading_is_off_while_there_are_unsaved_edits`, `test_browse_and_create_do_not_open_another_file_over_unsaved_edits`, `test_a_staged_prompt_change_counts_as_unsaved`.
- **Run executed programs without asking.** The Run tab now lists the nodes that run programs (`workspace.program_nodes`: `RUN`, kernel/subprocess backends, code, command, container) and keeps Run off until "I have read them: run anyway" is ticked, whichever model is chosen. Status: fixed; tests `test_running_a_graph_with_a_program_needs_an_acknowledgement`, `test_a_graph_without_programs_runs_without_the_acknowledgement`.
- **The Run tab offered `mock` first.** The option keeps its value (tests and `GraphEditor.run` use it) but the page calls it "dry run: placeholder answers, no model". Status: fixed; `test_the_dry_run_is_not_called_mock_in_the_page`. A real model is still not the default: a click on Run must not bill by surprise.
- **The app trusted the machine it runs on.** Streamlit listens on all interfaces unless told otherwise, so the app (no login, saved API keys, reads folders) was open to the local network. `graf vis --edit` now passes `--server.address 127.0.0.1`; `--host ADDRESS` changes it and prints a warning for anything but this computer. Status: fixed; `test_the_app_listens_on_this_computer_unless_told_otherwise`. Still true: saved keys go into the process-wide `os.environ`, which is fine for one user on one computer.

## Efficiency

- Browse drew a picture for every card on every rerun. A card now has a "Show the picture" toggle. Fixed; `test_browse_draws_a_picture_only_when_asked`.
- `ui.show_graph` re-rendered the HTML on every rerun. `_graph_html` is cached (`st.cache_data`) on the graph's JSON. Fixed; `test_a_picture_is_made_once_per_graph_not_on_every_rerun`.
- The recipe search embedded the query on every rerun. `RecipeIndex` keeps the query vectors. Fixed; `test_a_query_is_embedded_once_however_often_it_is_searched`.

## Consistency and style

- Fixed: the stale docstrings of `02-edit.py` ("four pages") and `04-browse.py` ("needs no model"), and `CLAUDE.md` ("four page files", six listed). The CHANGELOG's older entry still says four pages and `03-transfer.py`; it is history and was left.
- Fixed: pages and `chat_ops.py` no longer reach into `editor._dump()` / `editor._undo`; `GraphEditor` has `can_undo` and `undo_depth`, and the chat uses `source()`.
- Fixed: one exception tuple for model calls, `ui.CHAT_ERRORS`, used by the Create and Edit chats. `show_graph` also catches `OSError` and `SubprocessError`, so a missing graphviz program is a warning (`test_a_picture_that_cannot_be_drawn_is_a_warning_even_for_a_missing_program`).
- Fixed, small: `return` is outside the `with st.sidebar:` block in `edit_page`; `io` and `check_app` are imported at the top; one YAML instance; Undo on Create uses `dataclasses.replace`.

## Test coverage

Everything uses `AppTest` with stubbed LLMs. Not covered: the Ace editor, the real iframe/Cytoscape, a live Ollama or LLM call. A short manual checklist before a release would catch what `AppTest` cannot: open, edit, Apply, Save, Undo, Create, Save, Open in Edit, Save again.
