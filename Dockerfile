# syntax=docker/dockerfile:1.8

FROM cdgatenbee/valis-wsi:1.2.0@sha256:4fd20b687ae0f08c47011753bc5083dca5ac65a454d3615589eddf6b14e3c419

WORKDIR /app

COPY pyproject.toml LICENSE README.md /app/

COPY src /app/src
COPY script.py /app/script.py

RUN pip install .

CMD [ "python3", "script.py" ]
