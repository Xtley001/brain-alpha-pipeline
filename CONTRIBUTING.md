# Contributing

Guidelines for contributing to the `brain-alpha-pipeline` repository and modular quantitative library suite.

## Development Setup

```bash
git clone https://github.com/Xtley001/brain-alpha-pipeline.git
cd brain-alpha-pipeline
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

> **Note on Modular Libraries:** To contribute to the 7 standalone quantitative libraries (`brain-alpha-core`, `brain-store`, `brain-decorrelator`, `brain-options`, `brain-sentiment`, `brain-risk-model`, `brain-synthesis`), see the dedicated repository at [Xtley001/brain-libraries](https://github.com/Xtley001/brain-libraries).

## Running Tests

Verify the complete pipeline integration test suite (104 tests):

```bash
pytest tests/ -v
```

## Pull Request Guidelines

1. Branch from `main` using descriptive branch names (`feat/new-decorrelation-axis` or `fix/sue-normalization`).
2. Adhere to `black` formatting and strict static type typing.
3. Alpha expressions must remain AST-deduplicable and pass sub-industry neutrality invariants.
4. Ensure all unit tests pass before opening a pull request.
5. Provide a concise summary of changes and reference relevant issues.

## Security Disclosures

For vulnerability disclosures, see [SECURITY.md](./SECURITY.md).
