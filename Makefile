VCS_REF ?= $(shell git describe --dirty --abbrev=10 --tags --always  2>/dev/null)
BUILD_DATE ?= $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")
VERSION ?= 1.0.0

PROJECT_TEAM ?= cyrbil
PROJECT_NAME ?= covid19-bot
PROJECT_ROOT ?= $(abspath $(dir $(lastword ${MAKEFILE_LIST})))
DOCKER_IMAGE ?= ${PROJECT_TEAM}/${PROJECT_NAME}:${VERSION}-${VCS_REF}

clean:
	docker stop "${PROJECT_NAME}_dev-tools" "${PROJECT_NAME}" || true
	docker wait "${PROJECT_NAME}_dev-tools" "${PROJECT_NAME}" || true
	docker rm "${PROJECT_NAME}_dev-tools" "${PROJECT_NAME}" || true

init:
	docker run \
	    --detach \
	    --name "${PROJECT_NAME}_dev-tools" \
	    --volume "${PROJECT_ROOT}:/app" \
	    --workdir "/app" \
	    --env "TERM=xterm-256color" \
	    python:3.8-buster \
	    /bin/bash -c 'trap : TERM INT; sleep infinity & wait' \
	|| exit 0 \
	&& docker exec "${PROJECT_NAME}_dev-tools" \
	    /bin/bash -c ' \
	        apt-get update \
	     && apt-get install -y make git \
	     && python3 -m pip install \
	            --no-deps \
	            --no-cache \
	            --require-hashes \
	            --requirement dev-requirements.txt \
	            --requirement requirements.txt' \
	&& echo -e "#!/bin/bash\nmake precommit" > "${PROJECT_ROOT}/.git/hooks/pre-commit"

precommit:
	docker exec --tty "${PROJECT_NAME}_dev-tools" \
	        python3 -m pre_commit run --all

build:
	docker build --rm --tag "${DOCKER_IMAGE}" \
	    --build-arg "BUILD_DATE=${BUILD_DATE}" \
	    --build-arg "VCS_REF=${VCS_REF}" \
	    --build-arg "VERSION=${VERSION}" \
	    .

run:
	docker run \
	    --rm -ti \
	    --name "${PROJECT_NAME}" \
	    "${DOCKER_IMAGE}"

lock.run%:
	docker exec --tty "${PROJECT_NAME}_dev-tools" \
	     python3 -m piptools compile \
	            --generate-hashes \
	            ${REQUIREMENTS_IN}

lock: export REQUIREMENTS_IN=requirements.in
lock: lock.run.prod

lock.dev: export REQUIREMENTS_IN=dev-requirements.in
lock.dev: lock.run.dev

.PHONY: checks
checks: check.syntax check.lint check.type check.doc check.imports check.security check.requirements check.ci

.PHONY: check.security
check.security:
	python3 -m bandit -r .

.PHONY: check.syntax
check.syntax:
	python3 -m black --diff --check --verbose app.py

.PHONY: check.type
check.type:
	python3 -m mypy app.py

.PHONY: check.imports
check.imports:
	python3 -m isort --diff app.py

.PHONY: check.doc
check.doc:
	python3 -m pydocstyle app.py

.PHONY: check.lint
check.lint:
	python3 -m pylint \
	    --jobs=0 \
	    --disable=missing-class-docstring \
	    --disable=missing-module-docstring \
	    --disable=missing-function-docstring \
	    app.py

.PHONY: check.requirements
check.requirements:
	python3 -m safety check --bare
