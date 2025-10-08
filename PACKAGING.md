# Packaging & Publishing

This project includes a minimal `pyproject.toml` so it can be built and installed via pip.

Build a source distribution and wheel locally:

```bash
python3 -m pip install --upgrade build twine
python3 -m build
```

After running `python3 -m build` you'll get files in the `dist/` folder.

Install locally from the generated wheel or sdist:

```bash
python3 -m pip install dist/ez_ip_updater-2.0.0-py3-none-any.whl
# or
python3 -m pip install dist/ez_ip_updater-2.0.0.tar.gz
```

Publishing to PyPI (test first):

```bash
python3 -m pip install --upgrade twine
python3 -m twine upload --repository testpypi dist/*
# Verify installation from testpypi
python3 -m pip install --index-url https://test.pypi.org/simple/ --no-deps ez-ip-updater

# When ready to publish to real PyPI
python3 -m twine upload dist/*
```

Continuous publishing via GitHub Actions

--------------------------------------

This repo includes a workflow `.github/workflows/publish.yml` that will build and publish
on every pushed tag that starts with `v` (for example `v2.0.0`). By default the workflow
publishes to TestPyPI. To enable it:

1. Go to the repo Settings → Secrets → Actions.
2. Add `TEST_PYPI_API_TOKEN` with a token created on <https://test.pypi.org/account/token/>.
3. Push a tag, e.g. `git tag v2.0.0 && git push origin v2.0.0`.

To publish to the real PyPI instead:

1. Create a token on <https://pypi.org/manage/account/token/>.
2. Add repository secret `PYPI_API_TOKEN` with that token.
3. Edit `.github/workflows/publish.yml` and set `PUBLISH_TO: pypi` in the workflow env.
