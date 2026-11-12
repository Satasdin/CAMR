export PS1='$ ' PATH="$HOME/.local/bin:$PATH"
cd ~/BurrowDemo/project
# Claude Code in print mode, allowed to use only Burrow's tools, in its default style with short answers.
c() { claude -p "$1" --allowedTools 'mcp__burrow__*' --settings '{"outputStyle":"default"}' --append-system-prompt 'Answer in at most five short lines of plain text, no tables, no headings.'; }
# One shelf question, showing only how the model got going: cache used, seconds to load it, tokens read, seconds before the first word.
kvq() { burrow kv ~/BurrowDemo/Notes ask Law/act-part-04b-obligations-and-breach.md "Within how many hours must a data controller notify the Data Commissioner of a breach?" --json "$@" \
  | jq '{used_saved_cache: .used_cache, seconds_loading_cache: (.loaded_seconds*100|round/100), tokens_the_model_read: .prompt_tokens, seconds_to_first_word: ((.loaded_seconds + .prompt_seconds)*100|round/100), answer_starts: (.answer|split("\n")[0])}'; }
MATH='A matatu carries 14 passengers per trip and makes 9 trips a day. How many passengers does it carry in 6 days?'
UGANDA="Under Uganda's Data Protection and Privacy Act, how many days does a data controller have to notify the authority of a breach?"
