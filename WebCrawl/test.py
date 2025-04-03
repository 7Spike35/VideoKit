import requests

kw = input()

headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Mobile Safari/537.36 Edg/134.0.0.0"
}
url = "https://search.bilibili.com/all?vt=53775050&keyword=%s&from_source=webtop_search&spm_id_from=333.1007&search_source=5" % kw

response = requests.get(url, headers=headers).text

print(response)

