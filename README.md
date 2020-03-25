# Covid-19 Bot

A bot that post updates about Covid-19 pandemic to a Slack channel

## Requirements

Minimal requirement is just `docker` or `Python3.8`

## Usage

The application uses `docker` for easier deployment. You can use the
`Makefile` commands to do all the tasks.

To run the application:

    export SLACK_WEBHOOK="https://hooks.slack.com/services/xxxxxx"
    export CHANNEL="#xxxxxx" # optional
    make build
    make run
    
## Contribute

You can install the environment, or use the `docker` environment.


### With `docker`:

    make init
    
### With local environment:

Install a `Python3.8` environment, and optionally create a `virtualenv`.

    make install
    
To run locally:

    export SLACK_WEBHOOK="https://hooks.slack.com/services/xxxxxx"
    export CHANNEL="#xxxxxx" # optional
    python3.8 app.py

### Testing

You can run the various checks with:

    make precommit
    
Or individual check (see list in `Makefile`):

    make check.lint
