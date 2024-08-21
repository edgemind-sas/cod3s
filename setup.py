"""COD3S Setup."""

from setuptools import setup, find_packages

# read version as __version__
exec(open("cod3s/version.py").read())


setup(
    name="cod3s",
    version=__version__,
    url="https://github.com/edgemind-sas/pyctools",
    author="Roland Donat",
    author_email="roland.donat@gmail.com, roland.donat@edgemind.net",
    maintainer="Roland Donat",
    maintainer_email="roland.donat@edgemind.net",
    keywords="Modelling",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.8",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    packages=find_packages(
        exclude=[
            "*.tests",
            "*.tests.*",
            "tests.*",
            "tests",
            "log",
            "log.*",
            "*.log",
            "*.log.*",
        ]
    ),
    description="COmplexe Dynamic Stochastic System Simulation librairy",
    license="MIT",
    platforms="ALL",
    python_requires=">=3.8",
    install_requires=[
        "pandas==2.2.2",
        "pydantic==2.7.1",
        "xlsxwriter==3.0.9",
        "plotly==5.13.1",
        "lxml==5.3.0",
        "colored==1.4.4",
        "PyYAML==6.0.2"
    ],
    zip_safe=False,
    scripts=[
        "bin/cod3s-project",
        "bin/cod3s-simulate",
    ],
)
