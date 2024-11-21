<h1 align="center">Lāčplēsis</h1>
<h4 align="center">A bot for the <a href="https://discord.com/invite/2xVdx5Q">osu!Latvia Discord server</a></h4>

## Features

- automatically link osu! accounts to discord accounts with discord activity
- assign discord roles corresponding to osu! country ranks
- post new top scores

## How to setup

1. Clone the repository
2. Install [uv](https://docs.astral.sh/uv/getting-started/installation/)
3. Run `uv sync` to install dependencies
4. Create `.env` file based on `.env.example` and modify src/config.py with your values
5. Run `uv run src/app.py` to start the bot

Alternatively, you can run it with docker-compose with the provided `docker-compose.yaml` and `docker-compose-without-postgres.yaml` files.
