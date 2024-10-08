from setuptools import setup, find_packages

setup(
    name="gui_tabs",
    version="0.1",
    packages=find_packages(),
    entry_points={
        "gui_tabs": [
            "dune = gui_tabs.dune:DuneTab",
            "sirius = gui_tabs.sirius:SiriusTab",
        ],
    },
)
