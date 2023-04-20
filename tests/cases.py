import os


def get_cases_from_path(pname):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    path = f"{dir_path}/{pname}"

    # cases = [x[0] for x in os.walk(path)]
    cases = [f.name for f in os.scandir(path) if f.is_dir()]

    return cases
