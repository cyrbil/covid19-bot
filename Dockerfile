#------------------------------------------------------------------------------
# Stage 1 → Configure image
#------------------------------------------------------------------------------
FROM python:3.8-slim-buster as base

# image information
LABEL org.label-schema.name "cyrbil/covid19-bot"
LABEL org.label-schema.description "Covid-19 pandemic bot"
LABEL org.label-schema.url "https://github.com/cyrbil/covid19-bot"
LABEL org.label-schema.vcs-url "https://github.com/cyrbil/covid19-bot"
LABEL org.label-schema.vendor "Cyril DEMINGEON <1126098+cyrbil@users.noreply.github.com>"
LABEL org.label-schema.schema-version "1.0"

# create user & group
RUN addgroup --system --gid 1000 app                                          \
 && adduser --system --disabled-password --disabled-login                     \
            --uid 1000 --gid 1000 app

# setup python to use the dependencies folder"
ENV PYTHONIOENCODING="utf-8" \
    PYTHONPATH="/opt/requirements:$PYTHONPATH" \
    PATH="/opt/requirements/bin:$PATH" \
    LD_LIBRARY_PATH="/opt/requirements:$LD_LIBRARY_PATH"

# application options
WORKDIR /app
ENTRYPOINT ["/usr/local/bin/python3", "/app/app.py"]


#------------------------------------------------------------------------------
# Stage 2 → Build dependencies
#------------------------------------------------------------------------------
FROM python:3.8-buster as build

# install locales
RUN apt-get update \
 && apt-get install -y locales \
 && echo "en_US.UTF-8 UTF-8" > /etc/locale.gen \
 && locale-gen

# install dependencies into a custom folder
COPY requirements.txt .
RUN python3 -m pip install                                                    \
        --no-deps                                                             \
        --no-cache                                                            \
        --require-hashes                                                      \
        --target=/opt/requirements                                            \
        --requirement requirements.txt


#------------------------------------------------------------------------------
# Stage 3 → Install application
#------------------------------------------------------------------------------
FROM base

# copy locales, dependencies and app into final image
COPY --chown=0:0 --from=build /opt/requirements /opt/requirements
COPY --chown=0:0 --from=build /usr/lib/locale /usr/lib/locale
COPY --chown=0:0 app.py ./

# revoke permissions
USER 1000:1000

# buid information
ARG BUILD_DATE
ARG VERSION
ARG VCS_REF
LABEL org.label-schema.build-date "${BUILD_DATE}"
LABEL org.label-schema.vcs-ref "${VCS_REF}"
LABEL org.label-schema.version "${VERSION}"
