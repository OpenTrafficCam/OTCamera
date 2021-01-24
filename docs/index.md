# Home

This is a documentation of all OTCamera modules and configuration variables.
OTCamera is part of the [OpenTrafficCam](https://opentrafficcam.org) project and is used to record videos of traffic over several hours or even days.

On the left side you can see the main module [record](record) along with the [config](config) and [status](status) module, which contain variables used across the entire code.

It is build completly automatically using:

- [MkDocs](https://www.mkdocs.org/) and
- [mkdocstrings](https://github.com/pawamoy/mkdocstrings) and
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) theme.

To work on the docs run the following command to get a live updating server. You have to run it on the [OTCamera dev pi](https://opentrafficcam.org/contribute/otcamera).

```bash
python mkdocs serve
```

The site will be publicly served as stativ site on github pages.

```bash
python -m mkdocs gh-deploy
```

This command will build the current site and push it to the OTCamera repository (branch: [gh-pages](https://github.com/OpenTrafficCam/OTCamera/tree/gh-pages)).
