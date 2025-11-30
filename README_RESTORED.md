# Restored Bot Files

This directory contains the bot files retrieved from the server `62.109.26.139` on 2025-12-01.

## Contents

- **okx_hedge_webapp/**: The Flask web interface (dashboard).
- **okx_hedge_bot1/**: The core bot logic, including the real `okx_api.py` implementation.
- **radarplus_yml_generator/**: Additional tool found on the server.

## Status

The `okx_hedge_bot1/okx_api.py` file has been verified to contain the actual API implementation (not stubs), meaning this is the working version of the bot.

## How to Run

You can now proceed to run the bot locally or deploy it. The web app expects `okx_hedge_bot1` to be in the parent directory relative to itself, which matches this structure.
