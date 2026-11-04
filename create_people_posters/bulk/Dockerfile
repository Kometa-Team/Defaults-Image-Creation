# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e
FROM python:3.13.15-slim-bookworm@sha256:2325bb286ec344af3e5898cc224b5844e2707ac6e26b1632516fd3edc84a5e26 AS runtime
ARG DEBIAN_SNAPSHOT=20261101T000000Z
RUN sed -i "s|http://deb.debian.org/debian-security|https://snapshot.debian.org/archive/debian-security/${DEBIAN_SNAPSHOT}/|g; s|http://deb.debian.org/debian|https://snapshot.debian.org/archive/debian/${DEBIAN_SNAPSHOT}/|g" /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Check-Valid-Until=false update \
    && apt-get install -y --no-install-recommends git ca-certificates util-linux \
    && dpkg-query -W > /usr/local/share/bulk-os-packages.txt \
    && rm -rf /var/lib/apt/lists/*
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LANG=C.UTF-8 LC_ALL=C.UTF-8
COPY create_people_posters/bulk/requirements.lock /tmp/requirements.lock
RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock
WORKDIR /opt/people
COPY LICENSE ./LICENSE
COPY create_people_posters/create_people_poster.py create_people_posters/poster_fonts.py \
     create_people_posters/people_workspaces.py create_people_posters/people_diagnostics.py \
     create_people_posters/people_process.py create_people_posters/github_inventory_core.py \
     create_people_posters/bulk*.py ./create_people_posters/
COPY create_people_posters/unicode*.py ./create_people_posters/
COPY create_people_posters/fonts/Comfortaa-Medium.ttf create_people_posters/fonts/Fuggles-Regular.ttf \
     create_people_posters/fonts/Inter-Light.ttf create_people_posters/fonts/Montserrat-SemiBold.ttf \
     create_people_posters/fonts/Montserrat-Light.ttf create_people_posters/fonts/OFL-Comfortaa.txt \
     create_people_posters/fonts/OFL-Fuggles.txt create_people_posters/fonts/OFL-Inter.txt \
     create_people_posters/fonts/OFL-Montserrat.txt ./create_people_posters/fonts/
COPY create_people_posters/assets/people/ ./create_people_posters/assets/people/
COPY create_people_posters/unicode/runtime-release-v3.json ./create_people_posters/.bulk-runtime.json
# Windows and Linux checkouts produce the same sealed Python/license bytes.
RUN python -c "from pathlib import Path; [(p.write_bytes(p.read_bytes().replace(b'\r\n',b'\n'))) for p in Path('create_people_posters').rglob('*') if p.suffix in {'.py','.txt'}]" \
    && python create_people_posters/unicode_runtime.py verify --manifest create_people_posters/.bulk-runtime.json
RUN mkdir /batches /pins /source && chown 1000:1000 /batches /pins
USER 1000:1000
STOPSIGNAL SIGTERM
ENTRYPOINT ["python", "-B", "-u", "/opt/people/create_people_posters/bulk_regenerate.py", "--require-readonly-source"]

FROM runtime AS test
USER root
COPY create_people_posters/bulk/test-requirements.lock /tmp/test-requirements.lock
RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/test-requirements.lock
COPY create_people_posters/tests/conftest.py create_people_posters/bulk/tests/test_bulk*.py \
     create_people_posters/tests/test_collection_poster.py create_people_posters/tests/test_pillow_poster.py ./create_people_posters/tests/
COPY create_people_posters/compare_collection.py create_people_posters/create_people_poster.ps1 \
     create_people_posters/sync_people_images.py create_people_posters/publish_people_github.py \
     create_people_posters/people_publication_state.py create_people_posters/people_github.py \
     create_people_posters/people_remote_inventory.py create_people_posters/people_batch_safety.py ./create_people_posters/
ENV PYTHONPATH=/opt/people:/opt/people/create_people_posters PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PEOPLE_CONFIG_DIR=/tmp/daily-fixture-config
USER 1000:1000
ENTRYPOINT ["python", "-B", "-m", "pytest", "-p", "no:cacheprovider"]
CMD ["create_people_posters/tests", "-q"]

FROM test AS unicode-test
# Successor tests are separate from the immutable historical Jost profile.
# Legacy files here are test evidence only; the release image excludes Jost.
COPY create_people_posters/fonts/Jost-260.ttf create_people_posters/fonts/OFL-Jost.txt ./create_people_posters/fonts/
COPY create_people_posters/bulk/runtime-release.json ./create_people_posters/bulk/runtime-release.json
COPY create_people_posters/unicode/tests/ ./create_people_posters/unicode/tests/
COPY create_people_posters/orchestrator.py create_people_posters/poster_renderer.py ./create_people_posters/
USER root
# Exec form matches ENTRYPOINT and avoids a shell injecting a PWD variable
# (the existing diagnostic guard correctly treats a configured PWD as secret).
# No production security/redaction policy is changed for this build fixture.
RUN --network=none ["python", "-B", "-m", "pytest", "-p", "no:cacheprovider", "create_people_posters/unicode/tests", "-q"]
USER 1000:1000
CMD ["create_people_posters/unicode/tests", "-q"]

FROM runtime AS release
