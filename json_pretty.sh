# Source - https://stackoverflow.com/a
# Posted by Evgeny Karpov, modified by community. See post 'Timeline' for change history
# Retrieved 2025-12-07, License - CC BY-SA 4.0

#/bin/bash

grep -Eo '"[^"]*" *(: *([0-9]*|"[^"]*")[^{}\["]*|,)?|[^"\]\[\}\{]*|\{|\},?|\[|\],?|[0-9 ]*,?' | awk '{if ($0 ~ /^[}\]]/ ) offset-=4; printf "%*c%s\n", offset, " ", $0; if ($0 ~ /^[{\[]/) offset+=4}'

