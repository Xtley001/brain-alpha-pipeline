# Contributing

Guidelines for contributing to the `brain-alpha-pipeline` repository and modular quantitative library suite.

## Development Setup

```bash
git clone https://github.com/Xtley001/brain-alpha-pipeline.git
cd brain-alpha-pipeline
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install -e ./brain_libraries/brain_core -e ./brain_libraries/brain_store -e ./brain_libraries/brain_decorrelator -e ./brain_libraries/brain_options -e ./brain_libraries/brain_sentiment -e ./brain_libraries/brain_risk_model -e ./brain_libraries/brain_synthesis
```

## Running Tests

Verify the complete test suite across all 7 libraries:

```bash
python brain_libraries/test_all.py
```

## Pull Request Guidelines

1. Branch from `main` using descriptive branch names (`feat/new-decorrelation-axis` or `fix/sue-normalization`).
2. Adhere to `black` formatting and strict static type typing.
3. Alpha expressions must remain AST-deduplicable and pass sub-industry neutrality invariants.
4. Ensure all unit tests pass before opening a pull request.
5. Provide a concise summary of changes and reference relevant issues.

## Security Disclosures

For vulnerability disclosures, see [SECURITY.md](./SECURITY.md).
