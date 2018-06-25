from cx_Freeze import setup, Executable

setup(
    name="test_posix_spawn",
    version="0.1",
    description="Example of using spawn with multiprocessing",
    executables=[Executable("playground/test_posix_spawn.py")]
)
