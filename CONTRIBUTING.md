# Contributing to AEGIS API

Thank you for your interest in contributing to **AEGIS API**!

This repository serves as the clean, stable Vercel deployment target for the AEGIS project. Contributions that improve deployment reliability, documentation, or developer experience are highly welcome.

## How to Contribute

### 1. Reporting Issues

- Use the [Issues](https://github.com/devtechedge/aegis_vercel/issues) tab
- Provide clear reproduction steps
- Include relevant logs from Vercel (especially from `/debug` endpoint)

### 2. Suggesting Improvements

- Open an issue with the label `enhancement`
- Describe the problem and your proposed solution

### 3. Pull Requests

1. Fork the repository
2. Create a new branch from `main`
3. Make your changes
4. Ensure the app still works locally (`uvicorn main:app --reload`)
5. Submit a Pull Request

## Development Setup

```bash
cd apps/api
pip install -r requirements.txt
uvicorn main:app --reload