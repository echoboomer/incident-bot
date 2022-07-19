FROM python:3.9 as base

# Copy only the relevant Python files into the container.
COPY ./backend/app /incident-bot/app
COPY ./backend/bot /incident-bot/bot
COPY ./backend/requirements.txt /incident-bot
COPY ./backend/config.py /incident-bot
COPY ./backend/main.py /incident-bot
COPY ./backend/templates /incident-bot/templates

# Set the work directory to the app folder.
WORKDIR /incident-bot

# Install Python dependencies.
RUN pip3 install --no-cache-dir -r requirements.txt

EXPOSE 3000

CMD ["python3", "main.py"]

FROM base as production
