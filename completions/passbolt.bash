# Bash completion for passbolt CLI
# Source with: source /path/to/completions/passbolt.bash

_passbolt_completions() {
    local cur prev words cword
    _init_completion || return

    local commands="copy search show list export totp tui"
    local global_opts="-c --config -q --quiet -h --help"

    if [[ ${cword} -eq 1 ]]; then
        COMPREPLY=($(compgen -W "${commands} ${global_opts}" -- "${cur}"))
        return
    fi

    case "${words[1]}" in
        copy|show|totp|export)
            if [[ "${prev}" == "--pick" || "${words[2]}" != -* ]]; then
                COMPREPLY=($(compgen -W "${global_opts} --pick" -- "${cur}"))
            else
                COMPREPLY=($(compgen -W "${global_opts} --pick" -- "${cur}"))
            fi
            ;;
        search|list)
            COMPREPLY=($(compgen -W "${global_opts} --json" -- "${cur}"))
            ;;
        tui)
            COMPREPLY=($(compgen -W "${global_opts}" -- "${cur}"))
            ;;
        *)
            COMPREPLY=($(compgen -W "${commands} ${global_opts}" -- "${cur}"))
            ;;
    esac
}

complete -F _passbolt_completions passbolt