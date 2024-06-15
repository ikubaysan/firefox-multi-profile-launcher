import os
import subprocess
import shutil
import argparse
import signal
import sys
import time
from modules.ProxyScrapeAPI import ProxyScrapeAPI, Proxy

def find_default_profile_dir():

    potential_default_paths = [
        os.path.abspath(os.path.expanduser("~/snap/firefox/common/.mozilla/firefox")),
        os.path.abspath(os.path.expanduser("~/.mozilla/firefox")),
    ]

    base_path = None
    for path in potential_default_paths:
        if os.path.exists(path):
            base_path = path
            break

    if not base_path:
        print(f"Default profile directory not found in: {potential_default_paths}")
        return None

    for folder in os.listdir(base_path):
        if folder.endswith('.default') or folder.endswith('.default-release'):
            return os.path.join(base_path, folder)
    return None


def clone_template_profile(template_profile_dir, cloned_profiles_dir, profile_base_name, count: int,
                           force: bool = False, proxy_list: list = None):
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

                if proxy_list:
                    proxy = proxy_list[i]
                    set_proxy_for_profile_prefs_js_file(prefs_path=os.path.join(profile_path, "prefs.js"),
                                                        proxy=proxy.server,
                                                        port=proxy.port)
                continue

        command = f"cp -r {template_profile_dir} {profile_path}"
        try:
            subprocess.run(command, shell=True, check=True)
            print(f"Cloned {profile_name} successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to clone {profile_name}: {e}")

        if proxy_list:
            proxy = proxy_list[i]
            set_proxy_for_profile_prefs_js_file(prefs_path=os.path.join(profile_path, "prefs.js"),
                                                proxy=proxy.server,
                                                port=proxy.port)


def set_proxy_for_profile_prefs_js_file(prefs_path: str, proxy: str, port: int) -> None:
    # Define the preferences we need to set
    required_prefs = {
        'user_pref("network.proxy.backup.ssl",': f'user_pref("network.proxy.backup.ssl", "{proxy}");\n',
        'user_pref("network.proxy.backup.ssl_port",': f'user_pref("network.proxy.backup.ssl_port", {port});\n',
        'user_pref("network.proxy.http",': f'user_pref("network.proxy.http", "{proxy}");\n',
        'user_pref("network.proxy.http_port",': f'user_pref("network.proxy.http_port", {port});\n',
        'user_pref("network.proxy.share_proxy_settings",': 'user_pref("network.proxy.share_proxy_settings", true);\n',
        'user_pref("network.proxy.ssl",': f'user_pref("network.proxy.ssl", "{proxy}");\n',
        'user_pref("network.proxy.ssl_port",': f'user_pref("network.proxy.ssl_port", {port});\n',
        'user_pref("network.proxy.type",': 'user_pref("network.proxy.type", 1);\n'
    }

    # Read the prefs.js file
    with open(prefs_path, 'r') as file:
        lines = file.readlines()

    # Track which preferences have been updated
    updated_prefs = set()

    # Modify the required preferences
    new_lines = []
    for line in lines:
        updated = False
        for pref in required_prefs:
            if line.startswith(pref):
                new_lines.append(required_prefs[pref])
                updated_prefs.add(pref)
                updated = True
                break
        if not updated:
            new_lines.append(line)

    # Add any missing preferences
    for pref, value in required_prefs.items():
        if pref not in updated_prefs:
            new_lines.append(value)

    # Write the modified preferences back to the prefs.js file
    with open(prefs_path, 'w') as file:
        file.writelines(new_lines)

    print(f"Set proxy {proxy}:{port} for {prefs_path}")


def run_firefox_with_cloned_profiles(cloned_profiles_dir, count, start_private):
    profile_paths = [os.path.abspath(os.path.join(cloned_profiles_dir, profile)) for profile in
                     os.listdir(cloned_profiles_dir)]
    print(f"Found {len(profile_paths)} profiles to run.")
    processes = []
    for i, profile_path in enumerate(profile_paths):
        if i >= count:
            print(f"Stopped early after running {count} profiles.")
            break
        command = ["firefox", "-profile", profile_path, "-no-remote", "-allow-downgrade"]
        if start_private:
            command.append("--private-window")
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setpgrp)
        processes.append(process)
        time.sleep(0.25)
    return processes


def main(keep_script_running: bool, clone_count: int, force: bool, template_profile_dir, cloned_profiles_dir,
         profile_base_name: str, start_private: bool, use_proxies: bool):

    valid_proxies = []
    if use_proxies:
        proxy_scrape_api = ProxyScrapeAPI(protocol='http', anonymity='elite')
        proxies = proxy_scrape_api.get_proxies()
        print(f"Retrieved {len(proxies)} untested proxies.")
        valid_proxies = proxy_scrape_api.filter_proxies(proxies, timeout=3, max_workers=25)
        if len(valid_proxies) == 0:
            print("No valid proxies found. Exiting...")
            sys.exit(1)

        if len(valid_proxies) > clone_count:
            print(f"Found {len(valid_proxies)} valid proxies, but only {clone_count} clones will be created.")
            valid_proxies = valid_proxies[:clone_count]

        print(f"We will create a profile for each of the {len(valid_proxies)} valid proxies.")
        clone_count = len(valid_proxies)
        print(f"Set clone count to {clone_count}.")

    clone_template_profile(template_profile_dir, cloned_profiles_dir, profile_base_name,
                           count=clone_count,
                           force=force,
                           proxy_list=valid_proxies)
    processes = run_firefox_with_cloned_profiles(cloned_profiles_dir, clone_count, start_private)

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

    """
    Example:

    python main.py --count=10 --template-dir=/home/something/my_template --keep-running --start-private --use-proxies
    
    """

    parser = argparse.ArgumentParser(description="Clone Firefox profiles and run Firefox instances with them.")
    parser.add_argument("--template-dir", type=str, help="Directory of the template profile.")
    parser.add_argument("--cloned-dir", type=str,
                        default=os.path.join(os.path.dirname(os.path.realpath(__file__)), "cloned_profiles"),
                        help="Directory to store cloned profiles.")
    parser.add_argument("--profile-base-name", type=str, default="custom_profile",
                        help="Base name for cloned profiles.")
    parser.add_argument("--keep-running", action="store_true",
                        help="Keep the script running while Firefox processes are active.")
    parser.add_argument("--count", type=int, default=2, help="Max number of profiles to clone and run.")
    parser.add_argument("--force", action="store_true", help="Force the cloning of profiles, even if they exist.")
    parser.add_argument("--start-private", action="store_true", help="Launch Firefox in private browsing mode.")
    parser.add_argument("--use-proxies", action="store_true", help="Create a profile for every valid proxy")

    args = parser.parse_args()

    if not args.template_dir:
        args.template_dir = find_default_profile_dir()
        if not args.template_dir:
            print(f"No default profile directory found. Please specify a template directory.")
            sys.exit(1)
        print(f"Using default profile directory: {os.path.abspath(args.template_dir)}")

    main(keep_script_running=args.keep_running, clone_count=args.count, force=args.force,
         template_profile_dir=args.template_dir, cloned_profiles_dir=args.cloned_dir,
         profile_base_name=args.profile_base_name, start_private=args.start_private,
         use_proxies=args.use_proxies)
