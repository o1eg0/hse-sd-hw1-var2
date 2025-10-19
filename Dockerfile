FROM python:3.13-slim
RUN pip install pipenv

WORKDIR /app

COPY Pipfile Pipfile.lock ./

RUN pipenv install --deploy --system

COPY . .

CMD ["python", "-m", "src"]