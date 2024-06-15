import requests
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

class Proxy:
    def __init__(self, server: str, port: int):
        self.server = server
        self.port = port
        self.full_address = f"{server}:{port}"

    def __repr__(self):
        return self.full_address

class ProxyScrapeAPI:
    def __init__(self, protocol: str = 'http', timeout: int = 10000, country: str = 'all', ssl: str = 'all', anonymity: str = 'all'):
        self.base_url = 'https://api.proxyscrape.com/v2/'
        self.protocol = protocol
        self.timeout = timeout
        self.country = country
        self.ssl = ssl
        self.anonymity = anonymity

    def get_proxies(self, request_type: str = 'displayproxies') -> List[Proxy]:
        params = {
            'request': request_type,
            'protocol': self.protocol,
            'timeout': self.timeout,
            'country': self.country,
            'ssl': self.ssl,
            'anonymity': self.anonymity
        }
        response = requests.get(self.base_url, params=params)
        response.raise_for_status()  # Raise an HTTPError if the HTTP request returned an unsuccessful status code
        proxy_list = response.text.splitlines()
        proxies = [Proxy(server=proxy.split(":")[0], port=int(proxy.split(":")[1])) for proxy in proxy_list]
        return proxies

    def test_proxy(self, proxy: Proxy, timeout: int = 5) -> bool:
        try:
            protocol = self.protocol.split(",")[0]  # Get the first protocol in case there are multiple
            if protocol == "socks4":
                proxies = {
                    "http": f"socks4://{proxy.full_address}",
                    "https": f"socks4://{proxy.full_address}"
                }
            elif protocol == "socks5":
                proxies = {
                    "http": f"socks5://{proxy.full_address}",
                    "https": f"socks5://{proxy.full_address}"
                }
            else:
                proxies = {
                    "http": f"http://{proxy.full_address}",
                    "https": f"http://{proxy.full_address}"
                }
            response = requests.get("https://www.youtube.com", proxies=proxies, timeout=timeout)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def filter_proxies(self, proxies: List[Proxy], timeout: int = 5, max_workers: int = 10) -> List[Proxy]:
        start_time = time.time()
        valid_proxies = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_proxy = {executor.submit(self.test_proxy, proxy, timeout): proxy for proxy in proxies}
            for future in as_completed(future_to_proxy):
                proxy = future_to_proxy[future]
                try:
                    if future.result():
                        valid_proxies.append(proxy)
                except Exception as e:
                    print(f"Proxy {proxy.full_address} generated an exception: {e}")
        end_time = time.time()
        duration_minutes = (end_time - start_time) / 60
        print(f"Filtered {len(proxies)} proxies to {len(valid_proxies)} valid proxies in {round(duration_minutes, 2)} minutes.")
        return valid_proxies

# Example usage
if __name__ == "__main__":
    proxy_scrape_api = ProxyScrapeAPI(protocol='http', anonymity='elite')
    proxies = proxy_scrape_api.get_proxies()
    print(f"Retrieved {len(proxies)} untested proxies.")
    valid_proxies = proxy_scrape_api.filter_proxies(proxies, timeout=3, max_workers=25)
    print(valid_proxies)
