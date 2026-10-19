from setuptools import find_packages, setup

package_name = "hiwin_user_py"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="user",
    maintainer_email="user@example.com",
    description="Template Python package: talk to the HIWIN RA6 MoveIt 2 stack from your own code.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            # Add your own nodes here: "<executable> = hiwin_user_py.<module>:main"
            "move_demo = hiwin_user_py.move_demo:main",
        ],
    },
)
