filekit/
├── filekit/
│   ├── cli.py          # All the logic
│   ├── __init__.py
│   └── __main__.py
├── tests/
│   └── test_cli.py     # 4 tests
├── .github/workflows/
│   └── ci.yml          # Auto-runs tests on push/PR
├── pyproject.toml
├── README.md
├── LICENSE (MIT)
└── .gitignore




unzip filekit.zip && cd filekit_repo
git init
git add .
git commit -m "Initial commit: FileKit file utility CLI"
# Create a repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/filekit.git
git push -u origin main
