# syntax=docker/dockerfile:1.8

FROM cdgatenbee/valis-wsi:1.1.0

RUN apt -y update && apt -y install libvips

WORKDIR /app

COPY pyproject.toml LICENSE README.md /app/

COPY src /app/src
COPY script.py /app/script.py

RUN pip install .

CMD [ "python3", "script.py" ]
