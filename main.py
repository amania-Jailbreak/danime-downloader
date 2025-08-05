#!/usr/bin/env python3

from pywidevine.cdm import Cdm
from pywidevine.device import Device
from pywidevine.pssh import PSSH
from bs4 import BeautifulSoup
import requests
import json
import re
import xml.etree.ElementTree as ET
import subprocess
import os
import tempfile
import base64
from urllib.parse import urljoin, urlparse
import sys
import argparse
from tqdm import tqdm
import time

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0"
)


class DAnimeDownloader:
    def __init__(self, cookies="", device_path="device.wvd"):
        self.cookies = cookies
        self.device_path = device_path
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
            }
        )

        if cookies:
            cookie_dict = {}
            for cookie in cookies.split("; "):
                if "=" in cookie:
                    key, value = cookie.split("=", 1)
                    cookie_dict[key] = value

            for key, value in cookie_dict.items():
                self.session.cookies.set(key, value, domain=".docomo.ne.jp")
                self.session.cookies.set(key, value, domain=".animestore.docomo.ne.jp")
        else:
            print("No cookies provided")

        if os.path.exists(device_path):
            self.device = Device.load(device_path)
            self.cdm = Cdm.from_device(self.device)
        else:
            print(f"Error: Device file not found: {device_path}")
            sys.exit(1)

    def get_anime_info(self, part_id, pbar=None):
        if pbar:
            pbar.set_description("Getting anime info")

        url = f"https://animestore.docomo.ne.jp/animestore/ci_pc?workId={part_id}"
        response = self.session.get(url)
        response.raise_for_status()
        html_content = response.text
        soup = BeautifulSoup(html_content, "html.parser")
        episode_container = soup.select_one(".episodeContainer")
        items = []
        if episode_container:
            item_modules = episode_container.select(".itemModule")
            for item in item_modules:
                a_tag = item.find("a")
                if a_tag:
                    part_id = a_tag["href"].split("partId=")[-1]
                    episode_number = item.select_one(".number")
                    episode_number = (
                        episode_number.get_text(strip=True) if episode_number else ""
                    )
                    episode_title = item.select_one("h3.line2 span")
                    episode_title = (
                        episode_title.get_text(strip=True) if episode_title else ""
                    )
                    items.append(
                        {
                            "part_id": part_id,
                            "episode_number": episode_number,
                            "episode_title": episode_title,
                        }
                    )
        return items

    def get_episode_info(self, part_id, pbar=None):
        if pbar:
            pbar.set_description("Getting episode info")

        url = (
            f"https://animestore.docomo.ne.jp/animestore/rest/WS030101?partId={part_id}"
        )
        response = self.session.get(url)
        response.raise_for_status()
        data = response.json()

        return data

    def get_video_info(self, part_id, pbar=None):

        url = f"https://animestore.docomo.ne.jp/animestore/rest/WS010105?viewType=5&partId={part_id}&defaultPlay=5"

        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Referer": "https://animestore.docomo.ne.jp/",
            "X-Requested-With": "XMLHttpRequest",
        }

        if pbar:
            pbar.set_description("Getting video info")
            pbar.update(5)

        response = self.session.get(url, headers=headers)
        response.raise_for_status()

        if pbar:
            pbar.update(5)

        data = response.json()

        if pbar:
            pbar.update(5)

        if "data" not in data:
            print("Error: Failed to get video information")
            return None

        video_data = data["data"]
        return video_data

    def search(self, query, limit=20, pbar=None):
        """Search for anime by title"""
        if pbar:
            pbar.set_description("Searching for anime")

        url = f"https://animestore.docomo.ne.jp/animestore/rest/WS000105"
        params = {
            "searchKey": query,
            "length": limit,
        }

        response = self.session.get(url, params=params)
        response.raise_for_status()

        if pbar:
            pbar.update(5)

        data = response.json()
        return data.get("data", [])

    def extract_mpd_info(self, mpd_url, pbar=None):

        if pbar:
            pbar.set_description("Analyzing MPD")

        response = self.session.get(mpd_url)
        response.raise_for_status()

        if pbar:
            pbar.update(3)

        mpd_content = response.text
        root = ET.fromstring(mpd_content)

        if pbar:
            pbar.update(3)

        key_id = None

        for elem in root.iter():
            if "default_KID" in elem.attrib:
                key_id = elem.attrib["default_KID"]
                break

            for attr_name, attr_value in elem.attrib.items():
                if "default_KID" in attr_name or "defaultKID" in attr_name:
                    key_id = attr_value
                    break

            if key_id:
                break

        if pbar:
            pbar.update(3)

        if not key_id:
            try:
                namespaces = {
                    "mpd": "urn:mpeg:dash:schema:mpd:2011",
                    "cenc": "urn:mpeg:cenc:2013",
                }
                key_id_elements = root.findall(".//*[@{urn:mpeg:cenc:2013}default_KID]")
                for elem in key_id_elements:
                    key_id = elem.get("{urn:mpeg:cenc:2013}default_KID")
                    if key_id:
                        break
            except Exception as e:
                pass

        if not key_id:
            print("Error: KeyID not found")
            return None, None

        pssh_data = None

        cenc_pssh_match = re.search(
            r"<cenc:pssh[^>]*>(.*?)</cenc:pssh>", mpd_content, re.DOTALL
        )
        if cenc_pssh_match:
            pssh_data = cenc_pssh_match.group(1).strip()

        if not pssh_data:
            pssh_match = re.search(r"<pssh[^>]*>(.*?)</pssh>", mpd_content, re.DOTALL)
            if pssh_match:
                pssh_data = pssh_match.group(1).strip()

        if pbar:
            pbar.update(3)

        if not pssh_data:
            if "<cenc:pssh>" in mpd_content and "</cenc:pssh>" in mpd_content:
                try:
                    pssh_start = mpd_content.find("<cenc:pssh>") + len("<cenc:pssh>")
                    pssh_end = mpd_content.find("</cenc:pssh>", pssh_start)
                    if pssh_start > 10 and pssh_end > pssh_start:
                        pssh_data = mpd_content[pssh_start:pssh_end].strip()
                except Exception as e:
                    pass

        if not pssh_data:
            namespaces = {
                "mpd": "urn:mpeg:dash:schema:mpd:2011",
                "cenc": "urn:mpeg:cenc:2013",
            }

            widevine_uuid = "urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed"
            widevine_uuid_upper = "urn:uuid:EDEF8BA9-79D6-4ACE-A3C8-27DCD51D21ED"

            search_patterns = [
                f'.//mpd:ContentProtection[@schemeIdUri="{widevine_uuid}"]',
                f'.//mpd:ContentProtection[@schemeIdUri="{widevine_uuid_upper}"]',
                f'.//ContentProtection[@schemeIdUri="{widevine_uuid}"]',
                f'.//ContentProtection[@schemeIdUri="{widevine_uuid_upper}"]',
            ]

            pssh_elements = []
            for pattern in search_patterns:
                try:
                    if "mpd:" in pattern:
                        elements = root.findall(pattern, namespaces)
                    else:
                        elements = root.findall(pattern)
                    if elements:
                        pssh_elements = elements
                        break
                except Exception as e:
                    continue

            for i, pssh_element in enumerate(pssh_elements):
                pssh_data_elements = pssh_element.findall(".//cenc:pssh", namespaces)
                if pssh_data_elements:
                    pssh_data = pssh_data_elements[0].text
                    if pssh_data and pssh_data.strip():
                        pssh_data = pssh_data.strip()
                        break

                pssh_data_elements = pssh_element.findall(".//pssh")
                if pssh_data_elements:
                    pssh_data = pssh_data_elements[0].text
                    if pssh_data and pssh_data.strip():
                        pssh_data = pssh_data.strip()
                        break

                for child in pssh_element:
                    if "pssh" in child.tag.lower():
                        pssh_data = child.text
                        if pssh_data and pssh_data.strip():
                            pssh_data = pssh_data.strip()
                            break

                if pssh_data:
                    break

        if not pssh_data:
            try:
                all_pssh_elements = root.findall(".//cenc:pssh", namespaces)
                if not all_pssh_elements:
                    all_pssh_elements = root.findall(".//pssh")

                for pssh_elem in all_pssh_elements:
                    pssh_data = pssh_elem.text
                    if pssh_data and pssh_data.strip():
                        pssh_data = pssh_data.strip()
                        break
            except Exception as e:
                pass

        if pbar:
            pbar.update(3)

        if not pssh_data:
            print("Error: PSSH not found")
            return key_id, None

        return key_id, pssh_data

    def get_license_keys(self, key_id, pssh_data, one_time_key, pbar=None):

        if pbar:
            pbar.set_description("Getting license")

        token_url = f"https://wv.animestore.docomo.ne.jp/RequestLicense/Tokens/?keyId={key_id}&oneTimeKey={one_time_key}"

        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Referer": "https://animestore.docomo.ne.jp/",
            "Origin": "https://animestore.docomo.ne.jp",
        }

        response = self.session.get(token_url, headers=headers)
        response.raise_for_status()

        if pbar:
            pbar.update(3)

        token_data = response.json()
        token = token_data["tokenInfo"]

        if pbar:
            pbar.update(2)

        pssh = PSSH(pssh_data)

        if pbar:
            pbar.update(2)

        session_id = self.cdm.open()

        if pbar:
            pbar.update(2)

        challenge = self.cdm.get_license_challenge(session_id, pssh)

        if pbar:
            pbar.update(3)

        license_response = self.session.post(
            "https://danime.drmkeyserver.com/widevine_license",
            data=challenge,
            headers={"AcquireLicenseAssertion": token},
        )
        license_response.raise_for_status()

        if pbar:
            pbar.update(3)

        self.cdm.parse_license(session_id, license_response.content)

        if pbar:
            pbar.update(2)

        keys = []
        for key in self.cdm.get_keys(session_id):
            if hasattr(key.kid, "hex"):
                kid_hex = key.kid.hex
            else:
                kid_hex = key.kid

            if hasattr(key.key, "hex"):
                key_hex = key.key.hex()
            else:
                key_hex = key.key

            key_info = {"kid": kid_hex, "key": key_hex, "type": key.type}
            keys.append(key_info)

        self.cdm.close(session_id)

        if pbar:
            pbar.update(2)

        return keys

    def select_best_quality(self, mpd_url, target_resolution=None, pbar=None):
        """Select the best quality video and audio URLs from MPD"""

        if pbar:
            pbar.set_description("Analyzing available qualities")

        response = self.session.get(mpd_url)
        response.raise_for_status()
        mpd_content = response.text

        root = ET.fromstring(mpd_content)
        namespaces = {"mpd": "urn:mpeg:dash:schema:mpd:2011"}

        base_url_elem = root.find(".//mpd:BaseURL", namespaces)
        if base_url_elem is not None:
            base_url = base_url_elem.text
            if not base_url.startswith("http"):
                base_url = urljoin(mpd_url, base_url)
        else:
            base_url = mpd_url.rsplit("/", 1)[0] + "/"

        video_qualities = []
        audio_qualities = []

        for adaptation in root.findall(".//mpd:AdaptationSet", namespaces):
            mime_type = adaptation.attrib.get("mimeType", "")

            if "video" in mime_type:
                for rep in adaptation.findall("mpd:Representation", namespaces):
                    width = int(rep.attrib.get("width", 0))
                    height = int(rep.attrib.get("height", 0))
                    bandwidth = int(rep.attrib.get("bandwidth", 0))

                    base_url_elem = rep.find("mpd:BaseURL", namespaces)
                    if base_url_elem is not None:
                        relative_url = base_url_elem.text
                        if relative_url.startswith("http"):
                            video_url = relative_url
                        else:
                            video_url = urljoin(base_url, relative_url)

                        video_qualities.append(
                            {
                                "width": width,
                                "height": height,
                                "bandwidth": bandwidth,
                                "url": video_url,
                                "resolution": f"{width}x{height}",
                            }
                        )

            elif "audio" in mime_type:
                for rep in adaptation.findall("mpd:Representation", namespaces):
                    bandwidth = int(rep.attrib.get("bandwidth", 0))

                    base_url_elem = rep.find("mpd:BaseURL", namespaces)
                    if base_url_elem is not None:
                        relative_url = base_url_elem.text
                        if relative_url.startswith("http"):
                            audio_url = relative_url
                        else:
                            audio_url = urljoin(base_url, relative_url)

                        audio_qualities.append(
                            {"bandwidth": bandwidth, "url": audio_url}
                        )

        # Sort video qualities by resolution (highest first)
        video_qualities.sort(key=lambda x: (x["height"], x["width"]), reverse=True)
        audio_qualities.sort(key=lambda x: x["bandwidth"], reverse=True)

        # Select video quality
        selected_video = None
        if target_resolution:
            # Try to find exact match
            for quality in video_qualities:
                if quality["resolution"] == target_resolution:
                    selected_video = quality
                    break

            # If exact match not found, try to find closest match
            if not selected_video:
                target_width, target_height = map(int, target_resolution.split("x"))
                best_match = None
                min_diff = float("inf")

                for quality in video_qualities:
                    diff = abs(quality["width"] - target_width) + abs(
                        quality["height"] - target_height
                    )
                    if diff < min_diff:
                        min_diff = diff
                        best_match = quality

                selected_video = best_match

        # If no target resolution or no match found, use highest quality
        if not selected_video and video_qualities:
            selected_video = video_qualities[0]

        # Select highest quality audio
        selected_audio = audio_qualities[0] if audio_qualities else None

        if selected_video:
            pass
        if selected_audio:
            pass

        return selected_video, selected_audio

    def show_quality_info(self, part_id, pbar=None):
        """Show available video qualities for specified part_id"""
        print(f"Quality info: part_id={part_id}")

        video_data = self.get_video_info(part_id, pbar)
        if not video_data:
            return False

        mpd_url = None
        content_urls = video_data.get("contentUrls", {})
        if content_urls:
            quality_order = ["middle", "low", "lowest"]
            for quality in quality_order:
                url = content_urls.get(quality)
                if url and url.strip():
                    mpd_url = url
                    break

        if not mpd_url:
            cast_content_uri = video_data.get("castContentUri")
            if cast_content_uri and cast_content_uri.strip():
                mpd_url = cast_content_uri

        if not mpd_url:
            print("Error: MPD URL not found")
            return False

        response = self.session.get(mpd_url)
        response.raise_for_status()
        mpd_content = response.text

        root = ET.fromstring(mpd_content)
        namespaces = {"mpd": "urn:mpeg:dash:schema:mpd:2011"}

        video_qualities = []
        audio_qualities = []

        for adaptation in root.findall(".//mpd:AdaptationSet", namespaces):
            mime_type = adaptation.attrib.get("mimeType", "")

            if "video" in mime_type:
                for rep in adaptation.findall("mpd:Representation", namespaces):
                    width = int(rep.attrib.get("width", 0))
                    height = int(rep.attrib.get("height", 0))
                    bandwidth = int(rep.attrib.get("bandwidth", 0))

                    video_qualities.append(
                        {
                            "width": width,
                            "height": height,
                            "bandwidth": bandwidth,
                            "resolution": f"{width}x{height}",
                        }
                    )

            elif "audio" in mime_type:
                for rep in adaptation.findall("mpd:Representation", namespaces):
                    bandwidth = int(rep.attrib.get("bandwidth", 0))
                    audio_qualities.append({"bandwidth": bandwidth})

        # Sort qualities
        video_qualities.sort(key=lambda x: (x["height"], x["width"]), reverse=True)
        audio_qualities.sort(key=lambda x: x["bandwidth"], reverse=True)

        print("\nVideo qualities:")
        for i, quality in enumerate(video_qualities):
            marker = " (default)" if i == 0 else ""
            print(f"  {quality['resolution']} - {quality['bandwidth']:,} bps{marker}")

        print("\nAudio qualities:")
        for i, quality in enumerate(audio_qualities):
            marker = " (default)" if i == 0 else ""
            print(f"  {quality['bandwidth']:,} bps{marker}")

        return True

    def download_and_decrypt(
        self, mpd_url, keys, output_path, target_resolution=None, pbar=None
    ):
        """Download video and audio, decrypt, and merge"""

        if not keys:
            print("Error: No decryption keys")
            return False

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Define file paths
                encrypted_video = os.path.join(temp_dir, "encrypted_video.mp4")
                encrypted_audio = os.path.join(temp_dir, "encrypted_audio.mp4")
                decrypted_video = os.path.join(temp_dir, "decrypted_video.mp4")
                decrypted_audio = os.path.join(temp_dir, "decrypted_audio.mp4")

                # Select best quality video and audio
                selected_video, selected_audio = self.select_best_quality(
                    mpd_url, target_resolution, pbar
                )

                if not selected_video or not selected_audio:
                    print("Error: Cannot select quality")
                    return False

                video_url = selected_video["url"]
                audio_url = selected_audio["url"]

                if pbar:
                    pbar.update(10)

                # Download video and audio directly using selected URLs
                if pbar:
                    pbar.set_description("Downloading video")

                headers = {"User-Agent": USER_AGENT}
                if self.cookies:
                    headers["Cookie"] = self.cookies

                with self.session.get(video_url, stream=True, headers=headers) as r:
                    r.raise_for_status()
                    with open(encrypted_video, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)

                if pbar:
                    pbar.update(25)
                    pbar.set_description("Downloading audio")

                with self.session.get(audio_url, stream=True, headers=headers) as r:
                    r.raise_for_status()
                    with open(encrypted_audio, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)

                if pbar:
                    pbar.update(25)

                if pbar:
                    pbar.set_description("Decrypting video")

                cmd_decrypt_video = ["mp4decrypt"]
                for key_info in keys:
                    cmd_decrypt_video.extend(
                        ["--key", f"{key_info['kid']}:{key_info['key']}"]
                    )
                cmd_decrypt_video.extend([encrypted_video, decrypted_video])

                result = subprocess.run(
                    cmd_decrypt_video,
                    capture_output=True,
                    text=True,
                    shell=True,
                    encoding="utf-8",
                    errors="ignore",
                )
                if result.returncode != 0:
                    print(f"Video decrypt error: {result.stderr}")
                    return False

                if pbar:
                    pbar.update(15)
                    pbar.set_description("Decrypting audio")

                cmd_decrypt_audio = ["mp4decrypt"]
                for key_info in keys:
                    cmd_decrypt_audio.extend(
                        ["--key", f"{key_info['kid']}:{key_info['key']}"]
                    )
                cmd_decrypt_audio.extend([encrypted_audio, decrypted_audio])

                result = subprocess.run(
                    cmd_decrypt_audio,
                    capture_output=True,
                    text=True,
                    shell=True,
                    encoding="utf-8",
                    errors="ignore",
                )
                if result.returncode != 0:
                    print(f"Audio decrypt error: {result.stderr}")
                    return False

                if pbar:
                    pbar.update(15)
                    pbar.set_description("Merging video and audio")

                cmd_merge = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    decrypted_video,
                    "-i",
                    decrypted_audio,
                    "-c",
                    "copy",
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    output_path,
                ]

                result = subprocess.run(
                    cmd_merge,
                    capture_output=True,
                    text=True,
                    shell=True,
                    encoding="utf-8",
                    errors="ignore",
                )
                if result.returncode != 0:
                    print(f"Merge error: {result.stderr}")
                    return False

                if pbar:
                    pbar.update(10)

                return True

        except Exception as e:
            print(f"Download error: {e}")
            return False

    def process_video(
        self,
        part_id,
        output_path=None,
        target_resolution=None,
        jellyfin_naming=False,
        season_number=1,
    ):
        """Process video for specified part_id"""

        with tqdm(
            total=100,
            desc="Processing",
            ncols=60,
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {elapsed}",
            ascii=False,
            leave=True,
        ) as pbar:
            video_data = self.get_video_info(part_id, pbar)
            if not video_data:
                return False

            one_time_key = video_data.get("oneTimeKey")
            if not one_time_key:
                print("Error: oneTimeKey not found")
                return False

            pbar.set_description("Getting MPD URL")
            mpd_url = None

            content_urls = video_data.get("contentUrls", {})
            if content_urls:
                quality_order = ["middle", "low", "lowest"]
                for quality in quality_order:
                    url = content_urls.get(quality)
                    if url and url.strip():
                        mpd_url = url
                        break

            if not mpd_url:
                cast_content_uri = video_data.get("castContentUri")
                if cast_content_uri and cast_content_uri.strip():
                    mpd_url = cast_content_uri

            if not mpd_url:
                web_initiator_uri = video_data.get("webInitiatorUri")
                if web_initiator_uri:
                    mpd_url = self.extract_mpd_from_html(web_initiator_uri)

            if not mpd_url:
                print("Error: MPD URL not found")
                return False

            pbar.update(5)
            key_id, pssh_data = self.extract_mpd_info(mpd_url, pbar)
            if not key_id or not pssh_data:
                print("Error: MPD analysis failed")
                return False

            keys = self.get_license_keys(key_id, pssh_data, one_time_key, pbar)
            if not keys:
                print("Error: License key acquisition failed")
                return False

            if not output_path:
                pbar.set_description("Generating filename")
                title = video_data.get("workTitle", "Unknown")
                episode_number = video_data.get("partDispNumber", "Unknown")
                episode_title = video_data.get("partTitle", "Unknown")

                import unicodedata

                def sanitize_filename(name):
                    name = unicodedata.normalize("NFC", str(name))
                    name = "".join(
                        char for char in name if unicodedata.category(char)[0] != "C"
                    )
                    forbidden_chars = r'[<>:"/\\|?*]'
                    name = re.sub(forbidden_chars, "_", name)
                    name = name.strip()
                    if not name:
                        name = "Unknown"
                    if len(name) > 100:
                        name = name[:100]
                    return name

                def extract_episode_number(episode_str):
                    """Extract numeric episode number from part_id (last 3 digits)"""
                    # part_idの下三桁からエピソード番号を取得（例：22435001 -> 001 -> 1）
                    try:
                        episode_from_id = int(part_id[-3:])
                        return episode_from_id
                    except:
                        # フォールバック：文字列から数字を抽出
                        numbers = re.findall(r"\d+", episode_str)
                        if numbers:
                            return int(numbers[0])
                        return 1

                safe_title = sanitize_filename(title)
                safe_episode_number = sanitize_filename(episode_number)
                safe_episode_title = sanitize_filename(episode_title)

                if jellyfin_naming:
                    # Jellyfin形式: "Series Name - S01E01 - Episode Title.mp4"
                    episode_num = extract_episode_number(episode_number)
                    jellyfin_filename = f"{safe_title} - S{season_number:02d}E{episode_num:02d} - {safe_episode_title}.mp4"

                    # Jellyfinの推奨ディレクトリ構造: Series Name/Season 01/
                    output_dir = os.path.join(
                        "output", safe_title, f"S{season_number:02d}"
                    )
                    os.makedirs(output_dir, exist_ok=True)

                    output_path = os.path.join(output_dir, jellyfin_filename)
                else:
                    # 従来形式
                    output_dir = os.path.join("output", safe_title)
                    os.makedirs(output_dir, exist_ok=True)

                    output_path = os.path.join(
                        output_dir, f"{safe_episode_number}_{safe_episode_title}.mp4"
                    )

            pbar.update(2)

            success = self.download_and_decrypt(
                mpd_url, keys, output_path, target_resolution, pbar
            )

            if success:
                pbar.set_description("Completed")
                pbar.update(100 - pbar.n)
                print(f"Output: {output_path}")
            else:
                print("Processing failed")

            return success

    def extract_mpd_from_html(self, web_initiator_uri):
        try:
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
                "Referer": "https://animestore.docomo.ne.jp/",
            }
            response = self.session.get(web_initiator_uri, headers=headers)
            response.raise_for_status()
            html_content = response.text
            mpd_pattern = r'https://[^"\s]+\.mpd[^"\s]*'
            mpd_matches = re.findall(mpd_pattern, html_content)

            if mpd_matches:
                return mpd_matches[0]
            else:
                return None

        except Exception as e:
            print(f"HTML analysis error: {e}")
            return None


def main():
    parser = argparse.ArgumentParser(
        description="dAnime Store Downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python main.py 22435001 -c "cookies_string"              # Download episode (highest quality)
  python main.py 22435001 --cookies-file cookies.txt      # Load cookies from file
  python main.py 22435001 -c "cookies" -o output.mp4      # Download with custom output
  python main.py 22435001 -c "cookies" -r 1280x720        # Download in 720p
  python main.py 22435001 -c "cookies" -d custom.wvd      # Use custom device file
  python main.py 22435001 -c "cookies" --quality-info     # Show available qualities
  python main.py 22435001 -c "cookies" --jellyfin         # Download with Jellyfin naming format
  python main.py 22435 -c "cookies" --jellyfin            # Download series with Jellyfin format
  python main.py 22435001 -c "cookies" --jellyfin --season 2  # Download as Season 2 episode
  python main.py 22435 -c "cookies" --work-info           # Get anime info
  python main.py 22435001 -c "cookies" --episode-info     # Get episode info

Note: Cookies are required for authentication. Get them from your browser's developer tools.
You can save cookies to a text file and use --cookies-file option for convenience.""",
    )

    parser.add_argument("part_id", help="Part ID or Work ID")
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument(
        "-r",
        "--resolution",
        help="Target resolution (e.g., 1920x1080, 1280x720, 852x480). Default: highest available",
    )
    parser.add_argument(
        "-c", "--cookies", help="Browser cookies string for authentication"
    )
    parser.add_argument(
        "--cookies-file",
        help="File containing browser cookies (one per line or as single string)",
    )
    parser.add_argument(
        "-d",
        "--device",
        default="device.wvd",
        help="Widevine device file path (default: device.wvd)",
    )
    parser.add_argument("--work-info", action="store_true", help="Get anime details")
    parser.add_argument(
        "--episode-info", action="store_true", help="Get episode details"
    )
    parser.add_argument(
        "--quality-info", action="store_true", help="Show available video qualities"
    )
    parser.add_argument(
        "--jellyfin",
        action="store_true",
        help="Use Jellyfin-compatible naming format: 'Series Name - S01E01 - Episode Title.mp4'",
    )
    parser.add_argument(
        "--season",
        type=int,
        default=1,
        help="Season number for Jellyfin naming format (default: 1)",
    )

    args = parser.parse_args()

    # Get cookies from argument or file
    cookies = ""
    if args.cookies:
        cookies = args.cookies
    elif args.cookies_file:
        try:
            with open(args.cookies_file, "r", encoding="utf-8") as f:
                cookies = f.read().strip()
        except FileNotFoundError:
            print(f"Error: Cookie file not found: {args.cookies_file}")
            sys.exit(1)
        except Exception as e:
            print(f"Error reading cookie file: {e}")
            sys.exit(1)

    # Check for required cookies
    if not cookies:
        print("Error: Cookies required")
        print("Use -c option or --cookies-file option")
        sys.exit(1)

    downloader = DAnimeDownloader(cookies=cookies, device_path=args.device)
    is_episode = len(args.part_id) == 8

    if args.work_info:
        if is_episode:
            print("Error: --work-info not available for episode IDs")
            sys.exit(1)
        response = downloader.get_anime_info(args.part_id)
        for item in response:
            print(
                f"Part ID: {item['part_id']}, Episode: {item['episode_number']}, Title: {item['episode_title']}"
            )
        return

    elif args.episode_info:
        if not is_episode:
            print("Error: --episode-info only available for episode IDs")
            sys.exit(1)
        response = downloader.get_episode_info(args.part_id)
        print(f"Title: {response['workTitle']}")
        print(f"Part ID: {response['partId']}")
        print(f"Episode: {response['partDispNumber']} {response['partTitle']}")
        print(f"Description: {response['partExp']}")
        print(f"Copyright: {response['partCopyright']}")
        print(f"Image URL: {response['mainScenePath']}")
        return

    elif args.quality_info:
        if not is_episode:
            print("Error: --quality-info only available for episode IDs")
            sys.exit(1)
        downloader.show_quality_info(args.part_id)
        return
    if is_episode:
        success = downloader.process_video(
            args.part_id, args.output, args.resolution, args.jellyfin, args.season
        )
    else:
        success = True
        with tqdm(
            total=100,
            desc="Processing",
            ncols=60,
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {elapsed}",
            ascii=False,
            leave=True,
        ) as pbar:
            anime_info = downloader.get_anime_info(args.part_id, pbar)
            for item in anime_info:
                part_id = item["part_id"]
                output_path = None
                if args.output:
                    output_path = os.path.join(
                        os.path.dirname(args.output), f"{part_id}.mp4"
                    )
                success &= downloader.process_video(
                    part_id, output_path, args.resolution, args.jellyfin, args.season
                )

    if success:
        print("Completed")
    else:
        print("Failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
