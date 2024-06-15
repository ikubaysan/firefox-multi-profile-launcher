import os
import subprocess
import shutil
import argparse
import signal
import sys
import time


def find_default_profile_dir(base_path):
    for folder in os.listdir(base_path):
        if folder.endswith('.default'):
            return os.path.join(base_path, folder)
    return None


def clone_template_profile(template_profile_dir, cloned_profiles_dir, profile_base_name, count: int,
                           force: bool = False):
    if not os.path.exists(cloned_profiles_dir):
        os.makedirs(cloned_profiles_dir)

    for i in range(count):
        profile_name = f"{profile_base_name}_{i}"
        profile_path = os.path.join(cloned_profiles_dir, profile_name)

        if os.path.exists(profile_path):
            if force:
                print(f"Profile {profile_name} exists. Forcing clone - deleting existing profile...")
                shutil.rmtree(profile_path)
            else:
                print(f"Profile {profile_name} already exists. Skipping clone...")
                continue

        command = f"cp -r {template_profile_dir} {profile_path}"
        try:
            subprocess.run(command, shell=True, check=True)
            print(f"Cloned {profile_name} successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to clone {profile_name}: {e}")


def run_firefox_with_cloned_profiles(cloned_profiles_dir, start_private):
    profile_paths = [os.path.abspath(os.path.join(cloned_profiles_dir, profile)) for profile in
                     os.listdir(cloned_profiles_dir)]
    print(f"Found {len(profile_paths)} profiles to run.")
    processes = []
    for profile_path in profile_paths:
        command = ["firefox", "-profile", profile_path, "-no-remote"]
        if start_private:
            command.append("--private-window")
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setpgrp)
        processes.append(process)
        time.sleep(0.25)
    return processes


def main(keep_script_running: bool, clone_count: int, force: bool, template_profile_dir, cloned_profiles_dir,
         profile_base_name, start_private):
    clone_template_profile(template_profile_dir, cloned_profiles_dir, profile_base_name, count=clone_count, force=force)
    processes = run_firefox_with_cloned_profiles(cloned_profiles_dir, start_private)

    if keep_script_running:
        try:
            while any(process.poll() is None for process in processes):
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            print("Stopping Firefox processes...")
            for process in processes:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                except ProcessLookupError:
                    pass
    else:
        print("Script completed. Firefox processes are running independently.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clone Firefox profiles and run Firefox instances with them.")
    parser.add_argument("--template-dir", type=str, help="Directory of the template profile.")
    parser.add_argument("--cloned-dir", type=str,
                        default=os.path.join(os.path.dirname(os.path.realpath(__file__)), "cloned_profiles"),
                        help="Directory to store cloned profiles.")
    parser.add_argument("--profile-base-name", type=str, default="custom_profile",
                        help="Base name for cloned profiles.")
    parser.add_argument("--keep-running", action="store_true",
                        help="Keep the script running while Firefox processes are active.")
    parser.add_argument("--count", type=int, default=2, help="Number of profiles to clone.")
    parser.add_argument("--force", action="store_true", help="Force the cloning of profiles, even if they exist.")
    parser.add_argument("--start-private", action="store_true", help="Launch Firefox in private browsing mode.")

    args = parser.parse_args()

    if not args.template_dir:
        default_path = os.path.expanduser("~/snap/firefox/common/.mozilla/firefox")
        args.template_dir = find_default_profile_dir(default_path)
        if not args.template_dir:
            print(f"No default profile directory found in {default_path}. Please specify a template directory.")
            sys.exit(1)
        print(f"Using default profile directory: {os.path.abspath(args.template_dir)}")

    main(keep_script_running=args.keep_running, clone_count=args.count, force=args.force,
         template_profile_dir=args.template_dir, cloned_profiles_dir=args.cloned_dir,
         profile_base_name=args.profile_base_name, start_private=args.start_private)
