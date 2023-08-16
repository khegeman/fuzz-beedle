#!/usr/bin/env just --justfile
# https://github.com/casey/just
# Also `brew install just`

set shell := ["bash", "-uc"] 

# Run `just f` to fuzz this project! :-)
alias f := fuzz
alias r := replay 

# The first recipe will be the default one (the one run if you just run `just` in the directory). We'll define the implementation later and just refer to it now.
default: default_impl

clear:
    rm .replay/*.json
fuzz:
    woke --debug fuzz -s 4f2a521550c29390 --passive -n 1 tests/test_beedle.py

replay:
    WOKE_REPLAY=1 woke --debug fuzz -s 4f2a521550c29390 --passive -n 1 tests/test_beedle.py

default_impl:
    # fun fact 1 - the $'...' syntax is called ANSI-C quoting and allows us to
    # interpret backslashes as in the C language.
    # fun fact 2 - removing the `=` after `--list-prefix` will not work,
    # (the error msg is `error: Found argument '- ' which wasn't expected, or isn't valid in this context`)
    # I'm not sure if this is a quirk of shell or a bug in Just
    @just --list --unsorted --justfile {{justfile()}} --list-heading $'Recipes:\n' --list-prefix='- '
