# Report Library Publishing

For China WeChat report-library website updates, publish the approved static
files to the production repository:

- Repository: `https://github.com/market-insights/market-insights.github.io.git`
- Branch: `main`
- Public URL: `https://market-insights.github.io/`

The nested `china-wechat-med-phar/public_share/` checkout is configured to use
this production repository and its `main` branch. Local branches prefixed
`legacy-yvonne-` and the local `gh-pages` branch are retained only as backups;
do not push them unless the user explicitly asks for a legacy-copy update.

Before confirming a publication, verify both the homepage card and the direct
report URL on `market-insights.github.io` show the new report period.
