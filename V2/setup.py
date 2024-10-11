from setuptools import setup, find_packages

setup(
    name="gui_tabs",
    version="0.1",
    packages=find_packages(),
    entry_points={
        "gui_tabs": [
            "1_dune = gui_tabs.dune:DuneTab",
            "2_sirius = gui_tabs.sirius:SiriusTab",
            "3_settings = gui_tabs.settings:SettingsTab",
        ],
    },
)
