#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pickle Match Kanto - Kanto pickleball search and matching service."""

from __future__ import annotations

import html
import json
import mimetypes
import os
import sqlite3
import sys
import traceback
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from picklematch_support import contact_panel


ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("PICKLEMATCH_DB_PATH", str(ROOT / "picklematch_kanto.sqlite")))
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8791"))
SITE_NAME = os.environ.get("PICKLEMATCH_SITE_NAME", "Pickle Match Kanto")
CONTACT_EMAIL = os.environ.get("PICKLEMATCH_CONTACT_EMAIL", "sapia.business@gmail.com").strip()
SITE_OPERATOR = os.environ.get("PICKLEMATCH_OPERATOR", "Pickle Match Kanto 運営事務局")
SITE_BASE_URL = os.environ.get("PICKLEMATCH_SITE_BASE_URL", "http://%s:%s" % (HOST, PORT)).rstrip("/")
TODAY = "2026-07-29"

AREA_OPTIONS = {
    "東京都": [
        "千代田区", "中央区", "港区", "新宿区", "文京区", "台東区", "墨田区",
        "江東区", "品川区", "目黒区", "大田区", "世田谷区", "渋谷区", "中野区",
        "杉並区", "豊島区", "北区", "荒川区", "板橋区", "練馬区", "足立区",
        "葛飾区", "江戸川区",
        "立川市", "武蔵野市", "三鷹市", "府中市", "昭島市", "調布市", "町田市",
        "小金井市", "小平市", "日野市", "東村山市", "国分寺市", "国立市", "狛江市",
        "東大和市", "清瀬市", "東久留米市", "武蔵村山市", "多摩市", "稲城市",
        "羽村市", "西東京市", "八王子市", "青梅市", "福生市", "あきる野市",
        "瑞穂町", "日の出町", "檜原村", "奥多摩町",
    ],
    "神奈川県": [
        "横浜市", "横浜市都筑区", "横浜市緑区", "横浜市港北区", "川崎市", "相模原市",
        "横須賀市", "鎌倉市", "藤沢市", "茅ヶ崎市", "平塚市", "小田原市", "厚木市",
        "大和市", "海老名市", "座間市", "逗子市", "三浦市", "秦野市", "伊勢原市",
        "南足柄市",
    ],
    "埼玉県": [
        "さいたま市", "川口市", "川越市", "所沢市", "越谷市", "草加市", "春日部市",
        "熊谷市", "上尾市", "戸田市", "和光市", "朝霞市", "新座市", "志木市",
        "富士見市", "ふじみ野市", "狭山市", "入間市", "飯能市", "東松山市", "深谷市",
        "秩父市", "久喜市",
    ],
    "千葉県": [
        "千葉県内", "千葉市", "船橋市", "市川市", "松戸市", "柏市", "流山市", "習志野市",
        "八千代市", "浦安市", "市原市", "成田市", "我孫子市", "鎌ケ谷市", "佐倉市",
        "印西市", "野田市", "木更津市", "館山市",
    ],
    "茨城県": [
        "水戸市", "つくば市", "土浦市", "守谷市", "取手市", "牛久市", "龍ケ崎市", "日立市",
        "ひたちなか市", "古河市", "筑西市", "つくばみらい市", "神栖市", "鹿嶋市", "大洗町",
    ],
    "栃木県": ["宇都宮市", "小山市", "栃木市", "足利市", "佐野市", "那須塩原市", "日光市", "真岡市", "矢板市", "鹿沼市", "さくら市"],
    "群馬県": ["前橋市", "高崎市", "伊勢崎市", "太田市", "館林市", "藤岡市", "桐生市", "渋川市", "みどり市"],
}

RECRUITMENT_TYPES = [
    "練習試合", "合同練習", "初心者向け練習会", "交流イベント", "メンバー募集", "単発参加者募集",
]
LEVELS = ["未経験歓迎", "初級", "初級〜中級", "中級", "中級〜上級", "オープン"]
TIME_BANDS = ["早朝", "午前", "日中", "夕方", "平日夜"]
LISTING_STATES = ["公開情報確認済み", "代表申請受付", "運営確認済み", "メール確認済み"]


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def slug(value: str) -> str:
    clean = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    clean = "-".join(part for part in clean.split("-") if part)
    return clean or uuid.uuid4().hex[:12]


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def row_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None


def kanto_seed_organizations() -> list[dict]:
    """Only organizations with an official site and a directly verifiable activity page."""
    return [
        {
            "organization_id": "org-chiba-pickleball-association",
            "profile_slug": "chiba-pickleball-association",
            "organization_name": "一般社団法人 千葉県ピックルボール協会",
            "area_group": "千葉県",
            "municipality": "千葉県内",
            "primary_venue": "千葉県内の体験会・大会・交流会会場",
            "venue_type": "屋内・屋外",
            "level_label": "未経験歓迎〜中級",
            "organization_type": "地域協会",
            "primary_time": "体験会・大会・交流会ごと",
            "practice_frequency": "公開日程に準ずる",
            "member_count": "公開情報で人数未確認",
            "atmosphere": "世代や国籍を超えた交流を目指す地域コミュニティ",
            "experience_ratio": "公開情報で未確認",
            "beginner_welcome": 1,
            "introduction": "千葉県を主な活動地域として、体験会、大会、講習会、交流の機会を案内する団体です。掲載内容は公式サイトの公開情報を要約しています。",
            "representative_comment": "",
            "official_url": "https://pickleball-chiba.com/profile/",
            "public_contact_email": "",
            "public_contact_consent": 0,
            "source_type": "団体公式Webサイト",
            "source_url": "https://pickleball-chiba.com/profile/",
            "last_checked_at": TODAY,
            "listing_state": "公開情報確認済み",
        },
        {
            "organization_id": "org-northport-pickleball-club",
            "profile_slug": "northport-pickleball-club",
            "organization_name": "ノースポートピックルボールクラブ（NPPC）",
            "area_group": "神奈川県",
            "municipality": "横浜市都筑区",
            "primary_venue": "茅ヶ崎台小学校体育館",
            "venue_type": "屋内",
            "level_label": "初級〜中級",
            "organization_type": "地域クラブ",
            "primary_time": "金曜 19:00-21:00",
            "practice_frequency": "毎週金曜",
            "member_count": "少人数制（公開情報）",
            "atmosphere": "待ち時間を減らし、集中して練習しやすい少人数制",
            "experience_ratio": "公開情報で未確認",
            "beginner_welcome": 0,
            "introduction": "横浜市都筑区の小学校体育館で、少人数での練習会を開催する地域クラブです。参加条件と最新の受付状況は公式サイトで確認してください。",
            "representative_comment": "",
            "official_url": "https://northportpickleball.jp/",
            "public_contact_email": "",
            "public_contact_consent": 0,
            "source_type": "団体公式Webサイト",
            "source_url": "https://northportpickleball.jp/",
            "last_checked_at": TODAY,
            "listing_state": "公開情報確認済み",
        },
        {
            "organization_id": "org-prex-tochigi",
            "profile_slug": "prex-tochigi",
            "organization_name": "P-REX（ピーレックス）",
            "area_group": "栃木県",
            "municipality": "さくら市",
            "primary_venue": "Pickleball Park（喜連川）",
            "venue_type": "屋外",
            "level_label": "未経験歓迎〜中級",
            "organization_type": "スクール・チーム",
            "primary_time": "スクール・イベントごと",
            "practice_frequency": "公開日程に準ずる",
            "member_count": "公開情報で人数未確認",
            "atmosphere": "専用コートを起点にスクール・チーム・イベントを運営",
            "experience_ratio": "公開情報で未確認",
            "beginner_welcome": 1,
            "introduction": "栃木県さくら市の専用屋外コートを拠点に、プレイ環境整備、スクール、チーム、イベントを運営する団体です。",
            "representative_comment": "",
            "official_url": "https://prex-tk.com/",
            "public_contact_email": "",
            "public_contact_consent": 0,
            "source_type": "団体公式Webサイト",
            "source_url": "https://prex-tk.com/",
            "last_checked_at": TODAY,
            "listing_state": "公開情報確認済み",
        },
    ]


def kanto_candidate_rows() -> list[tuple[str, str, str, str, str]]:
    partner_url = "https://www.pickleball-japan.org/branches-rules/partners"
    return [
        ("candidate-pickleball-asaka", "ピックルボール朝霞", "朝霞市", partner_url, "日本連盟の公開パートナー団体一覧で所在地と公式SNSを確認。団体本人の掲載確認待ち。"),
        ("candidate-pickleball-gunma-rps", "ピックルボール群馬RPS", "前橋市", partner_url, "日本連盟の公開パートナー団体一覧で所在地を確認。団体本人の掲載確認待ち。"),
        ("candidate-p-ai-gunma", "Pアイ群馬", "伊勢崎市", partner_url, "日本連盟の公開パートナー団体一覧で所在地と公式SNSを確認。団体本人の掲載確認待ち。"),
    ]


def seed_organization_rows(conn: sqlite3.Connection, organizations: list[dict]) -> None:
    for item in organizations:
        record = dict(item)
        record["public_status"] = "published"
        record["created_at"] = TODAY
        record["updated_at"] = TODAY
        keys = ",".join(record.keys())
        placeholders = ",".join("?" for _ in record)
        conn.execute(
            "insert or ignore into organizations (" + keys + ") values (" + placeholders + ")",
            tuple(record.values()),
        )


def seed_candidate_rows(conn: sqlite3.Connection, candidates: list[tuple[str, str, str, str, str]]) -> None:
    conn.executemany(
        """
        insert or ignore into organization_candidates
          (candidate_id, candidate_name, area_hint, source_url, evidence_text, created_at)
        values (?, ?, ?, ?, ?, ?)
        """,
        [(candidate_id, name, area_hint, source_url, evidence, TODAY) for candidate_id, name, area_hint, source_url, evidence in candidates],
    )


def normalize_kanto_scope(conn: sqlite3.Connection) -> None:
    legacy_areas = ("東京23区", "多摩東部", "多摩西部")
    placeholders = ",".join("?" for _ in legacy_areas)
    conn.execute("update organizations set area_group='東京都' where area_group in (" + placeholders + ")", legacy_areas)
    conn.execute("update recruitments set area_group='東京都' where area_group in (" + placeholders + ")", legacy_areas)


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        conn.executescript(
            """
            pragma foreign_keys = on;

            create table if not exists organizations (
              organization_id text primary key,
              profile_slug text unique not null,
              organization_name text not null,
              area_group text not null,
              municipality text not null,
              primary_venue text,
              venue_type text,
              level_label text,
              organization_type text,
              primary_time text,
              practice_frequency text,
              member_count text,
              atmosphere text,
              experience_ratio text,
              beginner_welcome integer not null default 0,
              introduction text,
              representative_comment text,
              official_url text,
              public_contact_email text,
              public_contact_consent integer not null default 0,
              source_type text not null,
              source_url text,
              last_checked_at text,
              listing_state text not null default '公開情報確認済み',
              public_status text not null default 'published',
              created_at text not null,
              updated_at text not null
            );

            create table if not exists representative_applications (
              application_id text primary key,
              organization_id text,
              organization_name text not null,
              area_group text not null,
              municipality text not null,
              primary_venue text,
              level_label text,
              organization_type text,
              practice_frequency text,
              member_count text,
              atmosphere text,
              beginner_welcome integer not null default 0,
              introduction text,
              official_url text,
              representative_name text not null,
              representative_email text not null,
              public_contact_email text,
              public_contact_consent integer not null default 0,
              evidence_url text,
              internal_memo text,
              status text not null default 'pending',
              received_at text not null
            );

            create table if not exists recruitments (
              recruitment_id text primary key,
              organization_id text,
              organization_name text not null,
              title text not null,
              recruitment_type text not null,
              level_label text not null,
              starts_at text,
              ends_at text,
              area_group text not null,
              municipality text not null,
              venue_name text,
              venue_type text,
              fee_label text,
              fee_amount integer,
              capacity_label text,
              beginner_welcome integer not null default 0,
              age_guidance text,
              time_band text,
              weekday_label text,
              notes text,
              contact_method text,
              source_type text not null,
              source_url text,
              listing_state text not null default '公開情報確認済み',
              status text not null default 'open',
              created_at text not null,
              updated_at text not null
            );

            create table if not exists organization_candidates (
              candidate_id text primary key,
              candidate_name text not null,
              area_hint text,
              source_url text,
              evidence_text text,
              review_status text not null default 'pending',
              internal_notes text,
              created_at text not null
            );

            create table if not exists reports (
              report_id text primary key,
              report_type text not null,
              target_name text,
              reporter_email text,
              detail text not null,
              status text not null default 'received',
              received_at text not null
            );

            create table if not exists contact_requests (
              contact_id text primary key,
              name text,
              email text not null,
              category text not null,
              message text not null,
              received_at text not null
            );

            create index if not exists idx_orgs_public_area on organizations(public_status, area_group, municipality);
            create index if not exists idx_recruitments_open_date on recruitments(status, starts_at);
            create index if not exists idx_representative_private_email on representative_applications(representative_email);
            """
        )
        count = conn.execute("select count(*) from organizations").fetchone()[0]
        if count:
            normalize_kanto_scope(conn)
            conn.execute(
                """
                update organizations
                   set public_contact_email='8ojipa@gmail.com',
                       public_contact_consent=1
                 where organization_id='org-hachioji-pickleball-association'
                   and coalesce(public_contact_email, '')=''
                """
            )
            seed_organization_rows(conn, kanto_seed_organizations())
            seed_candidate_rows(conn, kanto_candidate_rows())
            return

        orgs = [
            {
                "organization_id": "org-tokyo-pickleball-association",
                "profile_slug": "tokyo-pickleball-association",
                "organization_name": "一般社団法人 東京ピックルボール協会",
                "area_group": "東京23区",
                "municipality": "江戸川区",
                "primary_venue": "江戸川区を中心に都内各所",
                "venue_type": "屋内・屋外",
                "level_label": "未経験歓迎〜中級",
                "organization_type": "地域協会",
                "primary_time": "イベント・体験会ごと",
                "practice_frequency": "イベント・体験会ごと",
                "member_count": "公開情報で人数未確認",
                "atmosphere": "幅広い世代が始めやすい普及活動",
                "experience_ratio": "公開情報で未確認",
                "beginner_welcome": 1,
                "introduction": "東京都内でピックルボールの情報発信と普及を行う団体として、公式サイトの公開情報をもとに掲載しています。",
                "representative_comment": "",
                "official_url": "https://tokyo-pickleball.org/",
                "public_contact_email": "",
                "public_contact_consent": 0,
                "source_type": "団体公式Webサイト",
                "source_url": "https://tokyo-pickleball.org/",
                "last_checked_at": TODAY,
                "listing_state": "公開情報確認済み",
            },
            {
                "organization_id": "org-chiyoda-pickleball-association",
                "profile_slug": "chiyoda-pickleball-association",
                "organization_name": "千代田区ピックルボール協会（CPA）",
                "area_group": "東京23区",
                "municipality": "千代田区",
                "primary_venue": "千代田区内の練習会・講習会会場",
                "venue_type": "屋内",
                "level_label": "未経験歓迎〜中級",
                "organization_type": "地域協会",
                "primary_time": "練習会・講習会ごと",
                "practice_frequency": "月次で情報更新",
                "member_count": "公開情報で人数未確認",
                "atmosphere": "初めての参加を歓迎する地域コミュニティ",
                "experience_ratio": "公開情報で未確認",
                "beginner_welcome": 1,
                "introduction": "大会運営、練習会、講習会の開催や情報発信を行う千代田区の団体です。掲載内容は公式サイトの公開情報を要約しています。",
                "representative_comment": "",
                "official_url": "https://www.chiyoda-pickleball.com/",
                "public_contact_email": "",
                "public_contact_consent": 0,
                "source_type": "団体公式Webサイト",
                "source_url": "https://www.chiyoda-pickleball.com/",
                "last_checked_at": TODAY,
                "listing_state": "公開情報確認済み",
            },
            {
                "organization_id": "org-hachioji-pickleball-association",
                "profile_slug": "hachioji-pickleball-association",
                "organization_name": "八王子ピックルボール協会",
                "area_group": "多摩西部",
                "municipality": "八王子市",
                "primary_venue": "八王子市および近隣地域",
                "venue_type": "屋内・屋外",
                "level_label": "未経験歓迎〜中級",
                "organization_type": "地域協会",
                "primary_time": "イベント・体験会ごと",
                "practice_frequency": "定期体験会は不定期",
                "member_count": "公開情報で人数未確認",
                "atmosphere": "地域の普及・振興と協力団体の連携を重視",
                "experience_ratio": "公開情報で未確認",
                "beginner_welcome": 1,
                "introduction": "八王子市と近隣地域での普及・振興を目的に、イベントや体験の機会を案内しています。",
                "representative_comment": "",
                "official_url": "https://hachiojipa.tokyo/",
                "public_contact_email": "8ojipa@gmail.com",
                "public_contact_consent": 1,
                "source_type": "団体公式Webサイト",
                "source_url": "https://hachiojipa.tokyo/",
                "last_checked_at": TODAY,
                "listing_state": "公開情報確認済み",
            },
            {
                "organization_id": "org-hino-pickleball-association",
                "profile_slug": "hino-pickleball-association",
                "organization_name": "日野ピックルボール協会（HIPA）",
                "area_group": "多摩東部",
                "municipality": "日野市",
                "primary_venue": "日野市を中心とした地域会場",
                "venue_type": "屋内・屋外",
                "level_label": "未経験歓迎〜中級",
                "organization_type": "地域協会",
                "primary_time": "練習会・体験会・交流会ごと",
                "practice_frequency": "所属団体の活動をサポート",
                "member_count": "役員9名（2025年5月時点の公開情報）",
                "atmosphere": "年齢・国籍・性別を問わず楽しめる地域コミュニティ",
                "experience_ratio": "公開情報で未確認",
                "beginner_welcome": 1,
                "introduction": "日野市を中心に、地域のピックルボールクラブを支え、体験会・交流会・クリニックなどを行う団体です。",
                "representative_comment": "",
                "official_url": "https://hinopickleball.org/",
                "public_contact_email": "",
                "public_contact_consent": 0,
                "source_type": "団体公式Webサイト",
                "source_url": "https://hinopickleball.org/",
                "last_checked_at": TODAY,
                "listing_state": "公開情報確認済み",
            },
            {
                "organization_id": "org-hino-pickles",
                "profile_slug": "hino-pickles",
                "organization_name": "日野ピックルズ",
                "area_group": "多摩東部",
                "municipality": "日野市",
                "primary_venue": "日野市内を中心とした活動会場",
                "venue_type": "屋内・屋外",
                "level_label": "未経験歓迎〜中級",
                "organization_type": "地域クラブ",
                "primary_time": "公開スケジュールに準ずる",
                "practice_frequency": "公開スケジュールに準ずる",
                "member_count": "公開情報で人数未確認",
                "atmosphere": "年齢・国籍・性別を問わず楽しむことを重視",
                "experience_ratio": "公開情報で未確認",
                "beginner_welcome": 1,
                "introduction": "日野ピックルボール協会の所属クラブとして公開紹介されている地域クラブです。",
                "representative_comment": "",
                "official_url": "https://hinopickleball.org/",
                "public_contact_email": "",
                "public_contact_consent": 0,
                "source_type": "提携団体の公開紹介",
                "source_url": "https://hinopickleball.org/",
                "last_checked_at": TODAY,
                "listing_state": "公開情報確認済み",
            },
            {
                "organization_id": "org-chowa-shc",
                "profile_slug": "chowa-shc-pickleball",
                "organization_name": "調和SHC倶楽部 ピックルボール",
                "area_group": "多摩東部",
                "municipality": "調布市",
                "primary_venue": "調和小アリーナほか",
                "venue_type": "屋内",
                "level_label": "初級〜中級",
                "organization_type": "総合型地域スポーツクラブ",
                "primary_time": "毎月第1・第2・第4木曜日の夕方",
                "practice_frequency": "月3〜4回",
                "member_count": "公開情報で人数未確認",
                "atmosphere": "地域の総合型スポーツクラブが運営",
                "experience_ratio": "公開情報で未確認",
                "beginner_welcome": 1,
                "introduction": "調布市の総合型地域スポーツ・文化クラブが運営するピックルボール活動です。詳細な参加条件は公式案内で確認してください。",
                "representative_comment": "",
                "official_url": "https://www.npo-chowashc.jp/sports/pickleball/",
                "public_contact_email": "",
                "public_contact_consent": 0,
                "source_type": "団体公式Webサイト",
                "source_url": "https://www.npo-chowashc.jp/sports/pickleball/",
                "last_checked_at": TODAY,
                "listing_state": "公開情報確認済み",
            },
            {
                "organization_id": "org-oceano-keio",
                "profile_slug": "oceano-keio-pickleball",
                "organization_name": "Oceano（慶應義塾大学公認学生団体）",
                "area_group": "東京23区",
                "municipality": "港区",
                "primary_venue": "青山小学校 体育館ほか",
                "venue_type": "屋内",
                "level_label": "未経験歓迎〜初級",
                "organization_type": "学生団体",
                "primary_time": "公開イベントごと",
                "practice_frequency": "公開イベントごと",
                "member_count": "公開情報で人数未確認",
                "atmosphere": "一人参加でもペアを組みやすいオープンプレー",
                "experience_ratio": "公開情報で未確認",
                "beginner_welcome": 1,
                "introduction": "港区での公開オープンプレー情報をもとに掲載しています。団体への連絡は掲載元の案内を利用してください。",
                "representative_comment": "",
                "official_url": "https://play-pickleball.jp/",
                "public_contact_email": "",
                "public_contact_consent": 0,
                "source_type": "公開イベント情報",
                "source_url": "https://play-pickleball.jp/?events=%E3%80%90%E3%80%91%E7%AC%AC2%E5%BC%BE%E9%96%8B%E5%82%AC%E6%B1%BA%E5%AE%9A%EF%BC%81%E5%A4%8F%E3%81%AE%E3%83%94%E3%83%83%E3%82%AF%E3%83%AB%E3%83%9C%E3%83%BC%E3%83%AB%E3%80%8C%E3%82%AA%E3%83%BC%E3%83%97)",
                "last_checked_at": TODAY,
                "listing_state": "公開情報確認済み",
            },
        ]
        seed_organization_rows(conn, orgs + kanto_seed_organizations())

        recruitments = [
            {
                "recruitment_id": "recruit-tanashi-beginner-0802",
                "organization_id": "",
                "organization_name": "ティップネス田無店",
                "title": "初めての方でも安心 ピックルボール体験会",
                "recruitment_type": "初心者向け練習会",
                "level_label": "未経験歓迎",
                "starts_at": "2026-08-02 17:05",
                "ends_at": "2026-08-02 18:35",
                "area_group": "多摩東部",
                "municipality": "西東京市",
                "venue_name": "ティップネス田無店 Aスタジオ",
                "venue_type": "屋内",
                "fee_label": "会員 1,100円 / 非会員 1,375円",
                "fee_amount": 1375,
                "capacity_label": "8名（最少3名）",
                "beginner_welcome": 1,
                "age_guidance": "どなたでも",
                "time_band": "夕方",
                "weekday_label": "日曜",
                "notes": "ルールや基礎を学びながら体験する公開プログラムです。8月16日・30日にも開催案内があります。",
                "contact_method": "電話またはフロントで受付",
                "source_type": "主催者公式Webサイト",
                "source_url": "https://tip.tipness.co.jp/shop_info/SHP032/information/357nfx02euz8yyzllv.html",
                "listing_state": "公開情報確認済み",
            },
            {
                "recruitment_id": "recruit-tanashi-practice-0809",
                "organization_id": "",
                "organization_name": "ティップネス田無店",
                "title": "スキル練習から応用練習までのピックルボール練習会",
                "recruitment_type": "単発参加者募集",
                "level_label": "初級〜中級",
                "starts_at": "2026-08-09 17:05",
                "ends_at": "2026-08-09 18:35",
                "area_group": "多摩東部",
                "municipality": "西東京市",
                "venue_name": "ティップネス田無店 Aスタジオ",
                "venue_type": "屋内",
                "fee_label": "会員 1,100円 / 非会員 1,375円",
                "fee_amount": 1375,
                "capacity_label": "8名（最少3名）",
                "beginner_welcome": 0,
                "age_guidance": "基礎経験のある方",
                "time_band": "夕方",
                "weekday_label": "日曜",
                "notes": "スキル練習から試合を想定した応用練習までを行う公開プログラムです。8月23日にも開催案内があります。",
                "contact_method": "電話またはフロントで受付",
                "source_type": "主催者公式Webサイト",
                "source_url": "https://tip.tipness.co.jp/shop_info/SHP032/information/357nfx02euz8yyzllv.html",
                "listing_state": "公開情報確認済み",
            },
            {
                "recruitment_id": "recruit-pj-edogawa-open",
                "organization_id": "",
                "organization_name": "一般財団法人ピックルボール日本連盟",
                "title": "PJ江戸川オープン2026（仮称）",
                "recruitment_type": "交流イベント",
                "level_label": "オープン",
                "starts_at": "2026-08-08 09:00",
                "ends_at": "2026-08-09 18:00",
                "area_group": "東京23区",
                "municipality": "江戸川区",
                "venue_name": "江戸川区総合体育館",
                "venue_type": "屋内",
                "fee_label": "大会要項公開待ち",
                "fee_amount": 0,
                "capacity_label": "大会要項公開待ち",
                "beginner_welcome": 0,
                "age_guidance": "19+ / 35+ / 50+",
                "time_band": "日中",
                "weekday_label": "土日",
                "notes": "ミックスダブルス、男女シングルス・ダブルスのオープンカテゴリーを予定。エントリー方法などの詳細は主催者の大会要項で確認してください。",
                "contact_method": "主催者の大会案内を確認",
                "source_type": "主催者公式Webサイト",
                "source_url": "https://japanpickleball.org/games/detail6343/",
                "listing_state": "公開情報確認済み",
            },
            {
                "recruitment_id": "recruit-ikebukuro-openplay-0802",
                "organization_id": "",
                "organization_name": "Sansanピックルボールコート池袋",
                "title": "ゲスト参加可 オープンプレー（中級）",
                "recruitment_type": "単発参加者募集",
                "level_label": "中級",
                "starts_at": "2026-08-02 06:00",
                "ends_at": "2026-08-02 09:00",
                "area_group": "東京23区",
                "municipality": "豊島区",
                "venue_name": "Sansanピックルボールコート池袋",
                "venue_type": "会場案内を確認",
                "fee_label": "3,300円",
                "fee_amount": 3300,
                "capacity_label": "残り16名（確認時点）",
                "beginner_welcome": 0,
                "age_guidance": "中級者向け",
                "time_band": "早朝",
                "weekday_label": "日曜",
                "notes": "予約ページの公開枠を掲載しています。残席・開催状況は予約ページで必ず確認してください。",
                "contact_method": "予約ページから申込",
                "source_type": "予約ページ",
                "source_url": "https://reserva.be/spc_ikebukuro_event",
                "listing_state": "公開情報確認済み",
            },
            {
                "recruitment_id": "recruit-ikebukuro-50plus-0824",
                "organization_id": "",
                "organization_name": "Sansanピックルボールコート池袋",
                "title": "50歳以上の方向け ピックルボール体験会",
                "recruitment_type": "初心者向け練習会",
                "level_label": "未経験歓迎",
                "starts_at": "2026-08-24 14:00",
                "ends_at": "2026-08-24 16:00",
                "area_group": "東京23区",
                "municipality": "豊島区",
                "venue_name": "Sansanピックルボールコート池袋",
                "venue_type": "会場案内を確認",
                "fee_label": "詳細ページで確認",
                "fee_amount": 0,
                "capacity_label": "詳細ページで確認",
                "beginner_welcome": 1,
                "age_guidance": "50歳以上・未経験者向け",
                "time_band": "日中",
                "weekday_label": "月曜",
                "notes": "50歳以上でピックルボール未経験の方を対象とした公開イベントです。",
                "contact_method": "掲載元の詳細ページで確認",
                "source_type": "公開イベント情報",
                "source_url": "https://play-pickleball.jp/?calender=2026-08&post_type=events",
                "listing_state": "公開情報確認済み",
            },
            {
                "recruitment_id": "recruit-shibuya-family-0830",
                "organization_id": "",
                "organization_name": "渋谷区スポーツセンター掲載イベント",
                "title": "親子ピックルボール教室",
                "recruitment_type": "交流イベント",
                "level_label": "未経験歓迎",
                "starts_at": "2026-08-30 10:00",
                "ends_at": "2026-08-30 12:00",
                "area_group": "東京23区",
                "municipality": "渋谷区",
                "venue_name": "渋谷区スポーツセンター",
                "venue_type": "屋内",
                "fee_label": "詳細ページで確認",
                "fee_amount": 0,
                "capacity_label": "詳細ページで確認",
                "beginner_welcome": 1,
                "age_guidance": "親子向け",
                "time_band": "午前",
                "weekday_label": "日曜",
                "notes": "国際大会で活動する選手をコーチに招く親子向けの公開教室として案内されています。",
                "contact_method": "掲載元の詳細ページで確認",
                "source_type": "公開イベント情報",
                "source_url": "https://play-pickleball.jp/?calender=2026-08&post_type=events",
                "listing_state": "公開情報確認済み",
            },
            {
                "recruitment_id": "recruit-oceano-0730",
                "organization_id": "org-oceano-keio",
                "organization_name": "Oceano（慶應義塾大学公認学生団体）",
                "title": "夏のピックルボール オープンプレー",
                "recruitment_type": "交流イベント",
                "level_label": "未経験歓迎〜初級",
                "starts_at": "2026-07-30 12:00",
                "ends_at": "2026-07-30 18:00",
                "area_group": "東京23区",
                "municipality": "港区",
                "venue_name": "青山小学校 体育館",
                "venue_type": "屋内",
                "fee_label": "無料",
                "fee_amount": 0,
                "capacity_label": "申込フォームで確認",
                "beginner_welcome": 1,
                "age_guidance": "大学生（他大学生・友人同伴可）",
                "time_band": "日中",
                "weekday_label": "木曜",
                "notes": "その場でペアを組みながら進めるアメリカンスタイルのオープンプレーとして公開されています。",
                "contact_method": "掲載元の申込フォームから連絡",
                "source_type": "公開イベント情報",
                "source_url": "https://play-pickleball.jp/?events=%E3%80%90%E3%80%91%E7%AC%AC2%E5%BC%BE%E9%96%8B%E5%82%AC%E6%B1%BA%E5%AE%9A%EF%BC%81%E5%A4%8F%E3%81%AE%E3%83%94%E3%83%83%E3%82%AF%E3%83%AB%E3%83%9C%E3%83%BC%E3%83%AB%E3%80%8C%E3%82%AA%E3%83%BC%E3%83%97)",
                "listing_state": "公開情報確認済み",
            },
        ]
        for item in recruitments:
            item["status"] = "open"
            item["created_at"] = TODAY
            item["updated_at"] = TODAY
            keys = ",".join(item.keys())
            placeholders = ",".join("?" for _ in item)
            conn.execute(
                "insert into recruitments (" + keys + ") values (" + placeholders + ")",
                tuple(item.values()),
            )

        normalize_kanto_scope(conn)

        candidates = [
            ("candidate-kitazawa", "きたざわピックル", "世田谷区", "https://pickleball-portal.jp/circles/", "第三者の公開団体一覧で活動地域と初心者〜中級者向けの説明を確認。団体本人の掲載確認待ち。"),
            ("candidate-pickle-peak", "ピックルピーク", "世田谷区", "https://pickleball-portal.jp/circles/", "第三者の公開団体一覧で活動地域を確認。団体本人の掲載確認待ち。"),
        ] + kanto_candidate_rows()
        seed_candidate_rows(conn, candidates)


def public_org(item: dict) -> dict:
    item = dict(item)
    if not item.get("public_contact_consent"):
        item["public_contact_email"] = ""
    item.pop("public_contact_consent", None)
    return item


def list_organizations(params: dict) -> list[dict]:
    with db() as conn:
        rows = [public_org(dict(row)) for row in conn.execute(
            "select * from organizations where public_status='published'"
        ).fetchall()]
    q = (params.get("q", [""])[0] or "").strip().lower()
    area = (params.get("area", [""])[0] or "").strip()
    city = (params.get("municipality", [""])[0] or "").strip()
    level = (params.get("level", [""])[0] or "").strip()
    venue = (params.get("venue_type", [""])[0] or "").strip()
    beginner = (params.get("beginner", [""])[0] or "").strip()
    org_type = (params.get("organization_type", [""])[0] or "").strip()
    state = (params.get("listing_state", [""])[0] or "").strip()
    if q:
        rows = [r for r in rows if q in " ".join(str(r.get(k, "")).lower() for k in ("organization_name", "municipality", "primary_venue", "introduction"))]
    if area:
        rows = [r for r in rows if r["area_group"] == area]
    if city:
        rows = [r for r in rows if r["municipality"] == city]
    if level:
        rows = [r for r in rows if level in r.get("level_label", "")]
    if venue:
        rows = [r for r in rows if venue in r.get("venue_type", "")]
    if beginner == "1":
        rows = [r for r in rows if r.get("beginner_welcome")]
    if org_type:
        rows = [r for r in rows if r.get("organization_type") == org_type]
    if state:
        rows = [r for r in rows if r.get("listing_state") == state]
    sort = (params.get("sort", ["updated"])[0] or "updated")
    if sort == "name":
        rows.sort(key=lambda r: r["organization_name"])
    elif sort == "area":
        rows.sort(key=lambda r: (r["area_group"], r["municipality"], r["organization_name"]))
    else:
        rows.sort(key=lambda r: (r.get("updated_at", ""), r["organization_name"]), reverse=True)
    return rows


def get_organization(profile_slug: str) -> dict | None:
    with db() as conn:
        row = conn.execute(
            "select * from organizations where profile_slug=? and public_status='published'",
            (profile_slug,),
        ).fetchone()
    return public_org(dict(row)) if row else None


def list_recruitments(params: dict) -> list[dict]:
    with db() as conn:
        rows = [dict(row) for row in conn.execute(
            "select * from recruitments where status='open'"
        ).fetchall()]
    q = (params.get("q", [""])[0] or "").strip().lower()
    filters = {
        "area": "area_group",
        "municipality": "municipality",
        "level": "level_label",
        "recruitment_type": "recruitment_type",
        "time_band": "time_band",
        "venue_type": "venue_type",
        "weekday": "weekday_label",
    }
    if q:
        rows = [r for r in rows if q in " ".join(str(r.get(k, "")).lower() for k in ("organization_name", "title", "municipality", "venue_name", "notes"))]
    for param, column in filters.items():
        value = (params.get(param, [""])[0] or "").strip()
        if value:
            rows = [r for r in rows if value in str(r.get(column, ""))]
    if (params.get("beginner", [""])[0] or "") == "1":
        rows = [r for r in rows if r.get("beginner_welcome")]
    fee = (params.get("max_fee", [""])[0] or "").strip()
    if fee.isdigit():
        rows = [r for r in rows if not r.get("fee_amount") or r["fee_amount"] <= int(fee)]
    quick = (params.get("quick", [""])[0] or "").strip()
    if quick == "weekend":
        rows = [r for r in rows if r.get("weekday_label") in ("土曜", "日曜", "土日")]
    elif quick == "weeknight":
        rows = [r for r in rows if r.get("time_band") == "平日夜"]
    elif quick == "beginner":
        rows = [r for r in rows if r.get("beginner_welcome")]
    sort = (params.get("sort", ["date"])[0] or "date")
    if sort == "updated":
        rows.sort(key=lambda r: r.get("updated_at", ""), reverse=True)
    else:
        rows.sort(key=lambda r: (r.get("starts_at") or "9999", r.get("title")))
    return rows


def summary() -> dict:
    orgs = list_organizations({})
    posts = list_recruitments({})
    return {
        "organizations": len(orgs),
        "recruitments": len(posts),
        "areas": len({o["municipality"] for o in orgs} | {p["municipality"] for p in posts}),
        "verified": sum(1 for o in orgs if o["listing_state"] in ("運営確認済み", "メール確認済み")),
        "source_checked": sum(1 for o in orgs if o["listing_state"] == "公開情報確認済み"),
    }


BASE_CSS = r"""
:root{--ink:#17212f;--muted:#64748b;--line:#dbe4ed;--paper:#fff;--soft:#f3f7fb;--brand:#0f7a62;--accent:#e15b31;--blue:#2767a5;--warn:#9a6700;--max:1180px}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Hiragino Kaku Gothic ProN","Yu Gothic",Meiryo,sans-serif;line-height:1.65;letter-spacing:0}
a{color:#175ea6;text-decoration:none}a:hover{text-decoration:underline}button,input,select,textarea{font:inherit}button{cursor:pointer}.shell{max-width:var(--max);margin:0 auto;padding:0 24px}.topnote{background:var(--ink);color:#dce6ef;font-size:12px}.topnote .shell{padding-top:8px;padding-bottom:8px}.site-header{border-bottom:1px solid var(--line);background:#fff;position:sticky;top:0;z-index:30}.navrow{min-height:68px;display:flex;align-items:center;justify-content:space-between;gap:22px}.brand{display:flex;align-items:center;gap:11px;color:var(--ink);font-weight:800;font-size:18px;white-space:nowrap}.brand-mark{width:30px;height:30px;border-radius:5px;background:var(--brand);display:grid;place-items:center;color:#fff;font-size:14px}.site-nav{display:flex;align-items:center;gap:18px}.site-nav a{color:#415166;font-size:14px;font-weight:700}.site-nav a.active{color:var(--brand)}.nav-cta{background:var(--accent);border:1px solid var(--accent);color:#fff!important;padding:8px 12px;border-radius:5px}.mobile-nav{display:none;border:1px solid var(--line);border-radius:5px;background:#fff;color:var(--ink);width:38px;height:34px}.hero{min-height:490px;background-image:url("/assets/hero-pickleball.png");background-size:cover;background-position:center;display:flex;align-items:center;color:#fff}.hero-copy{width:min(550px,100%);padding:46px 0;text-shadow:0 2px 16px rgba(0,0,0,.55)}.eyebrow{font-size:13px;font-weight:800;letter-spacing:0;color:#d9f4e8;margin:0 0 10px}.hero h1{font-size:48px;line-height:1.18;margin:0 0 18px;letter-spacing:0}.hero h1 span{display:block;font-size:24px;margin-top:12px}.hero p{font-size:17px;max-width:500px;margin:0 0 25px}.actions{display:flex;flex-wrap:wrap;gap:10px}.btn{border:1px solid transparent;border-radius:5px;padding:11px 16px;font-weight:800;display:inline-flex;align-items:center;justify-content:center;gap:7px;text-decoration:none}.btn:hover{text-decoration:none}.btn-primary{background:var(--accent);border-color:var(--accent);color:#fff}.btn-secondary{background:#fff;border-color:#fff;color:var(--ink)}.btn-outline{background:#fff;border-color:#a9b8c7;color:var(--ink)}.btn-green{background:var(--brand);border-color:var(--brand);color:#fff}.stats-band{border-bottom:1px solid var(--line);background:#fff}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:0}.stat{padding:18px 18px;border-left:1px solid var(--line)}.stat:first-child{border-left:0}.stat b{display:block;font-size:23px;line-height:1.15}.stat span{color:var(--muted);font-size:12px;font-weight:700}.section{padding:54px 0}.section-soft{background:var(--soft);border-top:1px solid var(--line);border-bottom:1px solid var(--line)}.section-head{display:flex;align-items:end;justify-content:space-between;gap:16px;margin-bottom:22px}.section-head h2{font-size:27px;line-height:1.25;margin:0}.section-head p{margin:5px 0 0;color:var(--muted);font-size:14px}.section-link{font-size:14px;font-weight:800;white-space:nowrap}.quick-row{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:17px}.quick-chip{border:1px solid #bdcddd;background:#fff;border-radius:999px;padding:6px 11px;color:#34445a;font-size:13px;font-weight:800}.quick-chip:hover,.quick-chip.active{color:#fff;background:var(--brand);border-color:var(--brand)}.filter-bar{display:grid;grid-template-columns:1.35fr repeat(3,minmax(120px,1fr));gap:9px;border:1px solid var(--line);background:#fff;padding:13px;margin-bottom:14px}.field{display:flex;flex-direction:column;gap:5px}.field label{font-size:12px;color:#526377;font-weight:800}.field input,.field select,.field textarea{border:1px solid #bccada;border-radius:4px;background:#fff;color:var(--ink);min-height:39px;padding:8px 10px}.field textarea{min-height:120px;resize:vertical}.filter-bar .filter-action{display:flex;align-items:end}.filter-bar .btn{width:100%;min-height:39px}.recruitment-list{border-top:2px solid var(--ink);background:#fff}.recruitment-row{display:grid;grid-template-columns:150px 1fr 150px;gap:20px;padding:18px 4px;border-bottom:1px solid var(--line);align-items:start}.datebox{font-weight:800}.datebox b{display:block;font-size:19px}.datebox span{font-size:12px;color:var(--muted)}.listing-title{font-size:18px;font-weight:800;color:var(--ink);margin:0 0 5px}.listing-title:hover{color:#175ea6}.listing-meta{display:flex;flex-wrap:wrap;gap:7px 12px;color:#536579;font-size:13px}.listing-note{color:#536579;font-size:13px;margin:9px 0 0}.listing-side{font-size:13px;color:#526377}.listing-side b{display:block;color:var(--ink);font-size:14px}.pill{display:inline-flex;align-items:center;white-space:nowrap;border:1px solid #c8d4df;border-radius:999px;padding:3px 8px;font-size:12px;font-weight:800;background:#fff;color:#405168}.pill.ok{background:#e6f5ee;border-color:#b8dfcd;color:#0c694f}.pill.orange{background:#fff0ea;border-color:#f2c5b4;color:#b94a25}.pill.blue{background:#eaf2fb;border-color:#c9ddf3;color:#1c5a96}.pill.warn{background:#fff7df;border-color:#ead391;color:#8a5a00}.area-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:0;border-top:1px solid var(--line);border-left:1px solid var(--line)}.area-cell{padding:19px;border-right:1px solid var(--line);border-bottom:1px solid var(--line);background:#fff}.area-cell h3{font-size:17px;margin:0 0 5px}.area-cell p{margin:0;color:var(--muted);font-size:13px}.area-cell a{font-size:13px;font-weight:800}.how-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:0;border-top:1px solid var(--line);border-left:1px solid var(--line)}.how{padding:24px;border-right:1px solid var(--line);border-bottom:1px solid var(--line);background:#fff}.how-num{font-size:13px;color:var(--brand);font-weight:900}.how h3{font-size:18px;margin:6px 0}.how p{margin:0;color:var(--muted);font-size:14px}.page-hero{padding:43px 0 28px;border-bottom:1px solid var(--line);background:#fff}.crumb{font-size:12px;color:var(--muted);margin-bottom:10px}.page-hero h1{font-size:34px;line-height:1.28;margin:0}.page-hero p{color:var(--muted);max-width:760px;margin:8px 0 0}.content-grid{display:grid;grid-template-columns:minmax(0,1fr) 290px;gap:34px;padding:35px 0 60px}.sidepanel{border-top:2px solid var(--ink);padding-top:14px}.sidepanel h2{font-size:15px;margin:0 0 10px}.sidepanel p,.sidepanel li{font-size:13px;color:var(--muted)}.sidepanel ul{padding-left:19px;margin:0 0 18px}.toolbar{display:flex;align-items:end;gap:9px;flex-wrap:wrap;padding:14px 0}.toolbar .field{min-width:145px;flex:1}.results-meta{display:flex;align-items:center;justify-content:space-between;gap:14px;margin:6px 0 11px;font-size:13px;color:var(--muted)}.results-meta b{color:var(--ink)}.table-wrap{border:1px solid var(--line);overflow:auto;background:#fff}.data-table{width:100%;min-width:940px;border-collapse:collapse;font-size:14px}.data-table th{background:#f6f9fc;color:#3e5065;text-align:left;white-space:nowrap;border-bottom:1px solid var(--line);padding:11px 13px;font-size:12px}.data-table td{padding:13px;border-bottom:1px solid var(--line);vertical-align:top}.data-table tr:last-child td{border-bottom:0}.data-table .name{font-weight:800;color:var(--ink)}.data-table .sub{display:block;color:var(--muted);font-size:12px;margin-top:2px}.filter-button{width:21px;height:21px;border:0;background:transparent;color:#506277;padding:0;margin-left:4px}.filter-popover{position:fixed;z-index:60;width:235px;background:#fff;border:1px solid #aebdcb;box-shadow:0 8px 22px rgba(23,33,47,.16);padding:12px;display:none}.filter-popover.open{display:block}.filter-popover h3{margin:0 0 7px;font-size:13px}.filter-popover select{width:100%;border:1px solid #bccada;border-radius:4px;padding:7px}.profile-header{padding:35px 0 26px;border-bottom:1px solid var(--line)}.profile-kicker{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}.profile-header h1{font-size:36px;line-height:1.24;margin:0 0 8px}.profile-lead{margin:0;color:var(--muted);max-width:790px}.profile-grid{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:34px;padding:33px 0 58px}.profile-section{margin-bottom:34px}.profile-section h2{font-size:21px;border-bottom:2px solid var(--ink);padding-bottom:8px;margin:0 0 16px}.detail-list{display:grid;grid-template-columns:repeat(2,1fr);border-top:1px solid var(--line);border-left:1px solid var(--line)}.detail-list div{border-right:1px solid var(--line);border-bottom:1px solid var(--line);padding:11px 13px}.detail-list dt{font-size:12px;color:var(--muted);font-weight:800}.detail-list dd{margin:2px 0 0;font-weight:700;font-size:14px}.contact-panel{border:1px solid var(--line);border-top:3px solid var(--brand);padding:17px;background:#fff}.contact-panel h2{font-size:18px;line-height:1.35;margin:0 0 7px}.contact-panel p{font-size:13px;color:var(--muted);margin:0 0 14px}.contact-panel .btn{width:100%;margin-top:8px}.contact-private{background:#f4f8fb;border:1px solid var(--line);padding:14px;font-size:13px;color:#526377}.form-layout{max-width:840px;padding:35px 0 60px}.form-intro{border-left:4px solid var(--brand);background:var(--soft);padding:14px 16px;margin-bottom:20px;color:#405168;font-size:14px}.form-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px 16px}.span-2{grid-column:span 2}.form-actions{display:flex;align-items:center;gap:12px;margin-top:20px}.form-result{display:none;margin-top:18px;border:1px solid #b8dfcd;background:#eff9f4;color:#1e6049;padding:12px;font-size:14px}.form-result.error{border-color:#efc1b2;background:#fff1ed;color:#a63b1e}.legal{max-width:820px;padding:38px 0 64px}.legal h2{font-size:21px;border-bottom:1px solid var(--line);padding-bottom:8px;margin-top:31px}.legal p,.legal li{font-size:14px;color:#405168}.legal ul{padding-left:20px}.site-footer{border-top:1px solid var(--line);background:#fff;padding:28px 0;color:#64748b}.footer-grid{display:grid;grid-template-columns:1.2fr 2fr;gap:30px}.footer-grid p{font-size:13px;margin:5px 0}.footer-links{display:flex;flex-wrap:wrap;gap:8px 18px;align-content:start}.footer-links a{font-size:13px;color:#516277}.empty{padding:26px;border:1px dashed #b8c6d2;color:#65768a;background:#fff;font-size:14px}.notice{border-left:4px solid var(--accent);padding:11px 14px;background:#fff6f2;color:#6d3a2b;font-size:13px;margin:14px 0}.small{font-size:12px;color:var(--muted)}.mobile-only{display:none}
@media(max-width:900px){.site-nav{display:none}.site-nav.open{display:flex;position:absolute;top:68px;left:0;right:0;padding:14px 24px;background:#fff;border-bottom:1px solid var(--line);flex-direction:column;align-items:flex-start;gap:10px}.mobile-nav{display:block}.hero{min-height:465px;background-position:61% center}.hero h1{font-size:40px}.stats{grid-template-columns:repeat(2,1fr)}.stat:nth-child(3){border-left:0;border-top:1px solid var(--line)}.stat:nth-child(4){border-top:1px solid var(--line)}.filter-bar{grid-template-columns:repeat(2,1fr)}.filter-bar .field:first-child{grid-column:span 2}.recruitment-row{grid-template-columns:126px 1fr}.listing-side{grid-column:2}.area-grid,.how-grid{grid-template-columns:1fr}.content-grid,.profile-grid{grid-template-columns:1fr}.sidepanel{border-top:1px solid var(--line);padding-top:22px}.footer-grid{grid-template-columns:1fr}.profile-header h1{font-size:31px}}
@media(max-width:620px){.shell{padding-left:16px;padding-right:16px}.topnote{font-size:11px}.hero{min-height:450px;background-position:64% center}.hero-copy{padding:30px 0}.hero h1{font-size:33px}.hero h1 span{font-size:20px}.hero p{font-size:15px}.actions{flex-direction:column;align-items:stretch}.btn{width:100%}.section{padding:40px 0}.section-head{display:block}.section-link{display:inline-block;margin-top:10px}.filter-bar{grid-template-columns:1fr}.filter-bar .field:first-child{grid-column:auto}.recruitment-row{display:block;padding:16px 0}.datebox{margin-bottom:8px}.listing-side{margin-top:10px}.area-grid,.how-grid{display:block;border-left:0}.area-cell,.how{border-left:1px solid var(--line)}.page-hero{padding:30px 0 22px}.page-hero h1{font-size:29px}.toolbar{display:grid;grid-template-columns:1fr 1fr}.toolbar .field{min-width:0}.toolbar .field:first-child{grid-column:span 2}.results-meta{align-items:flex-start}.detail-list{grid-template-columns:1fr}.form-grid{grid-template-columns:1fr}.span-2{grid-column:auto}.form-actions{display:block}.form-actions .btn{margin-top:8px}.mobile-only{display:inline}.hide-mobile{display:none}.profile-header h1{font-size:28px}}
@media(max-width:900px){.content-grid{grid-template-columns:minmax(0,1fr);min-width:0}}
@media(max-width:620px){.toolbar{grid-template-columns:repeat(2,minmax(0,1fr))}.toolbar .field input,.toolbar .field select{min-width:0;width:100%}}
"""


def icon_filter() -> str:
    return '<svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M3 5h18l-7 8v5l-4 2v-7L3 5z"/></svg>'


def nav(active: str) -> str:
    items = [
        ("/", "トップ", "home"),
        ("/recruitments", "募集掲示板", "recruitments"),
        ("/organizations", "団体DB", "organizations"),
        ("/representative", "団体代表者登録", "representative"),
    ]
    links = "".join(
        '<a class="' + ("active" if key == active else "") + '" href="' + href + '">' + label + "</a>"
        for href, label, key in items
    )
    return (
        '<div class="topnote"><div class="shell">関東1都6県を対象に、公開情報の確認日と出典を明示して掲載しています。</div></div>'
        '<header class="site-header"><div class="shell navrow">'
        '<a class="brand" href="/"><span class="brand-mark">P</span><span>' + esc(SITE_NAME) + '</span></a>'
        '<nav class="site-nav" id="siteNav">' + links + '<a class="nav-cta" href="/post-recruitment">募集する</a></nav>'
        '<button class="mobile-nav" id="mobileNav" aria-label="メニューを開く">☰</button>'
        "</div></header>"
    )


def footer() -> str:
    return (
        '<footer class="site-footer"><div class="shell footer-grid">'
        '<div><a class="brand" href="/"><span class="brand-mark">P</span><span>' + esc(SITE_NAME) + '</span></a>'
        '<p>練習相手も、仲間も、ここで見つかる。</p><p>関東1都6県のピックルボール団体・練習会・プレイヤーをつなぐ検索と募集の場です。</p></div>'
        '<div class="footer-links">'
        '<a href="/recruitments">募集掲示板</a><a href="/organizations">団体DB</a><a href="/representative">団体代表者登録</a><a href="/post-recruitment">募集投稿</a>'
        '<a href="/operator">運営者情報</a><a href="/privacy">プライバシーポリシー</a><a href="/terms">利用規約</a><a href="/about-data">掲載情報・訂正削除方針</a><a href="/contact">お問い合わせ</a>'
        '</div></div></footer>'
    )


def base_page(title: str, active: str, content: str, script: str = "") -> str:
    content = content.replace("Pickle Match Tokyo", esc(SITE_NAME)).replace("東京都内", "関東1都6県")
    content = content.replace(esc(SITE_NAME) + " 運営事務局", esc(SITE_OPERATOR))
    return (
        '<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="description" content="関東1都6県のピックルボール団体・練習会・参加者募集を探せるPickle Match Kanto。">'
        '<title>' + esc(title) + ' | ' + esc(SITE_NAME) + '</title><style>' + BASE_CSS + '</style></head><body>'
        + nav(active) + content + footer()
        + '<script>var menu=document.getElementById("mobileNav");if(menu){menu.onclick=function(){document.getElementById("siteNav").classList.toggle("open")}}</script>'
        + script + "</body></html>"
    )


def option_tags(values: list[str], first: str) -> str:
    return '<option value="">' + esc(first) + "</option>" + "".join('<option value="' + esc(v) + '">' + esc(v) + "</option>" for v in values)


def municipality_options() -> str:
    groups = []
    for area, cities in AREA_OPTIONS.items():
        groups.append('<optgroup label="' + esc(area) + '">' + "".join('<option value="' + esc(city) + '">' + esc(city) + "</option>" for city in cities) + "</optgroup>")
    return '<option value="">区・市を選ぶ</option>' + "".join(groups)


def home_page() -> str:
    body = """
    <main>
      <section class="hero"><div class="shell"><div class="hero-copy">
        <p class="eyebrow">KANTO PICKLEBALL MATCHING &amp; SEARCH</p>
        <h1>Pickle Match Kanto<span>練習相手も、仲間も、ここで見つかる。</span></h1>
        <p>関東1都6県の練習試合、合同練習、初心者向け練習会、交流イベント、メンバー募集を、出典と更新日を見ながら探せます。</p>
        <div class="actions"><a class="btn btn-primary" href="/recruitments">募集中を見る</a><a class="btn btn-secondary" href="/post-recruitment">募集する</a></div>
      </div></div></section>
      <section class="stats-band"><div class="shell stats">
        <div class="stat"><b id="statRecruitments">-</b><span>公開中の募集</span></div>
        <div class="stat"><b id="statOrganizations">-</b><span>公開団体</span></div>
        <div class="stat"><b id="statAreas">-</b><span>区・市をカバー</span></div>
        <div class="stat"><b>関東1都6県</b><span>東京都・神奈川・埼玉・千葉・茨城・栃木・群馬</span></div>
      </div></section>
      <section class="section" id="recruitments"><div class="shell">
        <div class="section-head"><div><h2>募集中はこちら</h2><p>参加者募集・練習会・イベントを、日時と条件で比較。</p></div><a class="section-link" href="/recruitments">募集掲示板をすべて見る →</a></div>
        <div class="quick-row"><button class="quick-chip" data-quick="weekend">今週末</button><button class="quick-chip" data-quick="weeknight">平日夜</button><button class="quick-chip" data-quick="beginner">初心者歓迎</button></div>
        <form class="filter-bar" id="homeRecruitmentFilters">
          <div class="field"><label for="homeQ">キーワード</label><input id="homeQ" name="q" placeholder="団体名・会場名・条件で検索"></div>
          <div class="field"><label for="homeArea">エリア</label><select id="homeArea" name="area">""" + option_tags(list(AREA_OPTIONS.keys()), "すべてのエリア") + """</select></div>
          <div class="field"><label for="homeCity">区・市</label><select id="homeCity" name="municipality">""" + municipality_options() + """</select></div>
          <div class="filter-action"><button class="btn btn-green" type="submit">条件で探す</button></div>
        </form>
        <div class="recruitment-list" id="homeRecruitmentList"><div class="empty">募集情報を読み込んでいます。</div></div>
      </div></section>
      <section class="section section-soft"><div class="shell">
        <div class="section-head"><div><h2>団体DBから、活動の場を見つける</h2><p>団体名、会場、レベル、初心者歓迎、登録状態を横並びで比較できます。</p></div><a class="section-link" href="/organizations">団体DBを見る →</a></div>
        <div class="area-grid">
          <div class="area-cell"><h3>東京都</h3><p>渋谷区、世田谷区、江東区、八王子市、立川市など</p><a href="/organizations?area=%E6%9D%B1%E4%BA%AC%E9%83%BD">エリアから探す →</a></div>
          <div class="area-cell"><h3>神奈川県</h3><p>横浜市、川崎市、相模原市、鎌倉市、藤沢市など</p><a href="/organizations?area=%E7%A5%9E%E5%A5%88%E5%B7%9D%E7%9C%8C">エリアから探す →</a></div>
          <div class="area-cell"><h3>埼玉県</h3><p>さいたま市、朝霞市、所沢市、川口市、越谷市など</p><a href="/organizations?area=%E5%9F%BC%E7%8E%89%E7%9C%8C">エリアから探す →</a></div>
          <div class="area-cell"><h3>千葉県</h3><p>千葉市、浦安市、市川市、船橋市、柏市など</p><a href="/organizations?area=%E5%8D%83%E8%91%89%E7%9C%8C">エリアから探す →</a></div>
          <div class="area-cell"><h3>茨城県</h3><p>つくば市、水戸市、取手市、守谷市、土浦市など</p><a href="/organizations?area=%E8%8C%A8%E5%9F%8E%E7%9C%8C">エリアから探す →</a></div>
          <div class="area-cell"><h3>栃木県</h3><p>宇都宮市、さくら市、小山市、栃木市、矢板市など</p><a href="/organizations?area=%E6%A0%83%E6%9C%A8%E7%9C%8C">エリアから探す →</a></div>
          <div class="area-cell"><h3>群馬県</h3><p>前橋市、高崎市、伊勢崎市、太田市、館林市など</p><a href="/organizations?area=%E7%BE%A4%E9%A6%AC%E7%9C%8C">エリアから探す →</a></div>
        </div>
      </div></section>
      <section class="section"><div class="shell">
        <div class="section-head"><div><h2>代表者の方へ</h2><p>団体情報の登録・修正と、募集投稿の申請を受け付けます。</p></div><a class="section-link" href="/representative">団体代表者登録へ →</a></div>
        <div class="how-grid">
          <div class="how"><div class="how-num">01</div><h3>団体情報を申請</h3><p>代表者名と代表メールは運営確認のみに使い、公開一覧・公開APIには出しません。</p></div>
          <div class="how"><div class="how-num">02</div><h3>公開内容を確認</h3><p>公開連絡用メールは、団体が掲載に同意したアドレスだけを公開します。</p></div>
          <div class="how"><div class="how-num">03</div><h3>募集を掲載</h3><p>練習試合、合同練習、初心者向け練習会など、最新の募集を掲載できます。</p></div>
        </div>
      </div></section>
    </main>
    """
    script = r"""
    <script>
    function e(v){var d=document.createElement("div");d.textContent=v==null?"":v;return d.innerHTML}
    function pill(v,c){return '<span class="pill '+(c||'')+'">'+e(v)+'</span>'}
    function fmt(d){if(!d)return "日程は掲載元で確認";var a=d.split(" ");return a[0].replaceAll("-","/")+" "+(a[1]||"")}
    function row(r){return '<article class="recruitment-row"><div class="datebox"><b>'+e(fmt(r.starts_at))+'</b><span>'+e(r.weekday_label||"")+" / "+e(r.time_band||"")+'</span></div><div><a class="listing-title" href="/recruitments?q='+encodeURIComponent(r.organization_name)+'">'+e(r.title)+'</a><div class="listing-meta">'+pill(r.recruitment_type,"orange")+pill(r.level_label,"blue")+pill(r.beginner_welcome?"初心者歓迎":"経験者向け",r.beginner_welcome?"ok":"")+'<span>'+e(r.municipality)+" / "+e(r.venue_name||"会場は掲載元で確認")+'</span></div><p class="listing-note">'+e(r.notes||"")+'</p></div><div class="listing-side"><b>'+e(r.organization_name)+'</b><span>'+e(r.fee_label||"費用は掲載元で確認")+'</span><br><a href="'+e(r.source_url)+'" target="_blank" rel="noopener">出典を見る</a></div></article>'}
    async function api(p){var r=await fetch(p);if(!r.ok)throw new Error("読み込みに失敗しました");return r.json()}
    var activeQuick="";
    async function loadPosts(){var f=document.getElementById("homeRecruitmentFilters"),qs=new URLSearchParams(new FormData(f));if(activeQuick)qs.set("quick",activeQuick);var rows=await api("/api/recruitments?"+qs.toString());document.getElementById("homeRecruitmentList").innerHTML=rows.slice(0,4).map(row).join("")||'<div class="empty">条件に合う公開中の募集はありません。団体DBから条件の近い団体を確認できます。</div>'}
    document.getElementById("homeRecruitmentFilters").onsubmit=function(x){x.preventDefault();loadPosts()};
    document.querySelectorAll("[data-quick]").forEach(function(b){b.onclick=function(){activeQuick=b.dataset.quick;document.querySelectorAll("[data-quick]").forEach(function(x){x.classList.remove("active")});b.classList.add("active");loadPosts()}});
    api("/api/summary").then(function(s){document.getElementById("statRecruitments").textContent=s.recruitments;document.getElementById("statOrganizations").textContent=s.organizations;document.getElementById("statAreas").textContent=s.areas}).catch(function(){});
    loadPosts().catch(function(){document.getElementById("homeRecruitmentList").innerHTML='<div class="empty">募集情報を取得できませんでした。</div>'});
    </script>
    """
    return base_page("トップ", "home", body, script)


def recruitment_page() -> str:
    body = """
    <main>
      <section class="page-hero"><div class="shell"><div class="crumb">Pickle Match Tokyo / 募集掲示板</div><h1>募集掲示板</h1><p>今週末、平日夜、初心者歓迎など、東京都内のピックルボール募集を条件から探せます。掲載日時・費用・残席は出典ページで最終確認してください。</p></div></section>
      <div class="shell content-grid"><section>
        <div class="quick-row"><button class="quick-chip" data-quick="weekend">今週末</button><button class="quick-chip" data-quick="weeknight">平日夜</button><button class="quick-chip" data-quick="beginner">初心者歓迎</button></div>
        <form class="filter-bar" id="recruitmentFilters">
          <div class="field"><label>キーワード</label><input name="q" placeholder="団体名・会場・募集内容"></div>
          <div class="field"><label>エリア</label><select name="area">""" + option_tags(list(AREA_OPTIONS.keys()), "すべてのエリア") + """</select></div>
          <div class="field"><label>区・市</label><select name="municipality">""" + municipality_options() + """</select></div>
          <div class="field"><label>募集種別</label><select name="recruitment_type">""" + option_tags(RECRUITMENT_TYPES, "すべての募集種別") + """</select></div>
          <div class="field"><label>レベル</label><select name="level">""" + option_tags(LEVELS, "すべてのレベル") + """</select></div>
          <div class="field"><label>曜日</label><select name="weekday">""" + option_tags(["月曜", "火曜", "水曜", "木曜", "金曜", "土曜", "日曜", "土日"], "すべての曜日") + """</select></div>
          <div class="field"><label>時間帯</label><select name="time_band">""" + option_tags(TIME_BANDS, "すべての時間帯") + """</select></div>
          <div class="field"><label>屋内・屋外</label><select name="venue_type">""" + option_tags(["屋内", "屋外"], "すべて") + """</select></div>
          <div class="field"><label>参加費</label><select name="max_fee"><option value="">指定なし</option><option value="1000">1,000円以下</option><option value="2000">2,000円以下</option><option value="4000">4,000円以下</option></select></div>
          <div class="field"><label>並び順</label><select name="sort"><option value="date">開催日順</option><option value="updated">更新日順</option></select></div>
          <div class="filter-action"><button class="btn btn-green" type="submit">絞り込む</button></div>
        </form>
        <label class="small"><input type="checkbox" id="beginnerOnly"> 初心者歓迎のみ表示</label>
        <div class="results-meta"><span><b id="postCount">0</b>件の募集</span><span>公開情報は最終確認日と出典を表示</span></div>
        <div class="recruitment-list" id="recruitmentList"><div class="empty">募集情報を読み込んでいます。</div></div>
      </section>
      <aside class="sidepanel"><h2>掲載情報について</h2><p>募集情報は主催者の公式Webサイト、公開SNS、または団体代表者からの申請を出典にします。</p><ul><li>開催状況・残席・参加費は出典ページで確認</li><li>更新日順と開催日順を切り替え可能</li><li>なりすまし・誤情報は運営へ通報</li></ul><a class="btn btn-primary" href="/post-recruitment">募集を投稿する</a></aside>
      </div>
    </main>
    """
    script = r"""
    <script>
    function e(v){var d=document.createElement("div");d.textContent=v==null?"":v;return d.innerHTML}
    function pill(v,c){return '<span class="pill '+(c||'')+'">'+e(v)+'</span>'}
    function fmt(d){if(!d)return "日程は掲載元で確認";var a=d.split(" ");return a[0].replaceAll("-","/")+" "+(a[1]||"")}
    function row(r){return '<article class="recruitment-row"><div class="datebox"><b>'+e(fmt(r.starts_at))+'</b><span>'+e(r.weekday_label||"")+" / "+e(r.time_band||"")+'</span></div><div><h2 class="listing-title">'+e(r.title)+'</h2><div class="listing-meta">'+pill(r.recruitment_type,"orange")+pill(r.level_label,"blue")+pill(r.beginner_welcome?"初心者歓迎":"経験者向け",r.beginner_welcome?"ok":"")+'<span>'+e(r.municipality)+" / "+e(r.venue_name||"会場は掲載元で確認")+'</span><span>'+e(r.venue_type||"会場情報を確認")+'</span></div><p class="listing-note">'+e(r.notes||"")+'</p></div><div class="listing-side"><b>'+e(r.organization_name)+'</b><span>'+e(r.fee_label||"費用は掲載元で確認")+'</span><br><span>'+e(r.capacity_label||"人数は掲載元で確認")+'</span><br><a href="'+e(r.source_url)+'" target="_blank" rel="noopener">出典・申込先を見る</a></div></article>'}
    async function api(p){var r=await fetch(p);if(!r.ok)throw new Error("読み込みに失敗しました");return r.json()}
    var activeQuick="";
    async function load(){var form=document.getElementById("recruitmentFilters"),qs=new URLSearchParams(new FormData(form));if(document.getElementById("beginnerOnly").checked)qs.set("beginner","1");if(activeQuick)qs.set("quick",activeQuick);var rows=await api("/api/recruitments?"+qs.toString());document.getElementById("postCount").textContent=rows.length;document.getElementById("recruitmentList").innerHTML=rows.map(row).join("")||'<div class="empty">条件に合う募集はありません。条件を広げるか、団体DBから活動団体を確認してください。</div>'}
    document.getElementById("recruitmentFilters").onsubmit=function(x){x.preventDefault();load()};
    document.getElementById("beginnerOnly").onchange=load;
    document.querySelectorAll("[data-quick]").forEach(function(b){b.onclick=function(){activeQuick=b.dataset.quick;document.querySelectorAll("[data-quick]").forEach(function(x){x.classList.remove("active")});b.classList.add("active");load()}});
    load().catch(function(){document.getElementById("recruitmentList").innerHTML='<div class="empty">募集情報を取得できませんでした。</div>'});
    </script>
    """
    return base_page("募集掲示板", "recruitments", body, script)


def organizations_page() -> str:
    body = """
    <main>
      <section class="page-hero"><div class="shell"><div class="crumb">Pickle Match Tokyo / 団体DB</div><h1>団体DB</h1><p>東京都内の公開ピックルボール団体を、活動エリア・会場・レベル・登録状態で比較できます。ID列は公開しません。</p></div></section>
      <div class="shell content-grid"><section>
        <div class="toolbar">
          <div class="field"><label>団体名・会場を検索</label><input id="orgQ" placeholder="例: 調布、初心者、協会"></div>
          <div class="field"><label>エリア</label><select id="orgArea">""" + option_tags(list(AREA_OPTIONS.keys()), "すべて") + """</select></div>
          <div class="field"><label>区・市</label><select id="orgMunicipality">""" + municipality_options() + """</select></div>
          <div class="field"><label>並び順</label><select id="orgSort"><option value="updated">更新日順</option><option value="name">団体名順</option><option value="area">エリア順</option></select></div>
        </div>
        <div class="results-meta"><span><b id="orgCount">0</b>団体</span><span>列見出しの漏斗から条件を絞り込み</span></div>
        <div class="table-wrap"><table class="data-table"><thead><tr>
          <th>団体名<button class="filter-button" data-filter="search" aria-label="団体名で絞り込み">""" + icon_filter() + """</button></th>
          <th>活動エリア<button class="filter-button" data-filter="area" aria-label="エリアで絞り込み">""" + icon_filter() + """</button></th>
          <th>主な会場<button class="filter-button" data-filter="venue" aria-label="屋内屋外で絞り込み">""" + icon_filter() + """</button></th>
          <th>レベル感<button class="filter-button" data-filter="level" aria-label="レベルで絞り込み">""" + icon_filter() + """</button></th>
          <th>団体種別<button class="filter-button" data-filter="type" aria-label="団体種別で絞り込み">""" + icon_filter() + """</button></th>
          <th>主な活動時間</th><th>登録状態<button class="filter-button" data-filter="state" aria-label="登録状態で絞り込み">""" + icon_filter() + """</button></th><th>出典</th>
        </tr></thead><tbody id="orgRows"><tr><td colspan="8">読み込んでいます。</td></tr></tbody></table></div>
      </section>
      <aside class="sidepanel"><h2>DBの読み方</h2><ul><li>「公開情報確認済み」は出典URLと確認日を運営が確認した状態</li><li>「代表申請受付」は掲載修正・連絡先公開の申請受領済み</li><li>「運営確認済み」と「メール確認済み」は別々に表示</li></ul><p>団体の公式性や認定を表すものではありません。</p><a class="btn btn-primary" href="/representative">団体情報を申請</a></aside>
      </div>
    </main>
    <div class="filter-popover" id="filterPopover"><h3 id="filterTitle">絞り込み</h3><select id="filterSelect"></select></div>
    """
    script = r"""
    <script>
    function e(v){var d=document.createElement("div");d.textContent=v==null?"":v;return d.innerHTML}
    function pill(v,c){return '<span class="pill '+(c||'')+'">'+e(v)+'</span>'}
    async function api(p){var r=await fetch(p);if(!r.ok)throw new Error("読み込みに失敗しました");return r.json()}
    var filters={q:"",area:"",municipality:"",level:"",venue_type:"",beginner:"",organization_type:"",listing_state:"",sort:"updated"};
    var initialParams=new URLSearchParams(window.location.search);
    Object.keys(filters).forEach(function(key){if(initialParams.has(key))filters[key]=initialParams.get(key)||""});
    var configs={
      search:{title:"団体名を検索",input:true,key:"q"},
      area:{title:"活動エリア",values:["","東京都","神奈川県","埼玉県","千葉県","茨城県","栃木県","群馬県"],key:"area"},
      venue:{title:"屋内・屋外",values:["","屋内","屋外"],key:"venue_type"},
      level:{title:"レベル感",values:["","未経験歓迎","初級","中級","上級"],key:"level"},
      type:{title:"団体種別",values:["","地域協会","地域クラブ","総合型地域スポーツクラブ","学生団体"],key:"organization_type"},
      state:{title:"登録状態",values:["","公開情報確認済み","代表申請受付","運営確認済み","メール確認済み"],key:"listing_state"}
    };
    document.getElementById("orgQ").value=filters.q;
    document.getElementById("orgArea").value=filters.area;
    document.getElementById("orgMunicipality").value=filters.municipality;
    document.getElementById("orgSort").value=filters.sort;
    function row(o){var contact=o.public_contact_email?'<span class="sub">公開連絡先あり</span>':"";return '<tr><td><a class="name" href="/organizations/'+e(o.profile_slug)+'">'+e(o.organization_name)+'</a><span class="sub">'+e(o.organization_type||"")+'</span></td><td><b>'+e(o.area_group)+'</b><span class="sub">'+e(o.municipality)+'</span></td><td>'+e(o.primary_venue||"")+'<span class="sub">'+e(o.venue_type||"")+'</span></td><td>'+pill(o.level_label,"blue")+(o.beginner_welcome?'<span class="sub">初心者歓迎</span>':"")+'</td><td>'+e(o.organization_type||"")+'</td><td>'+e(o.primary_time||"")+'</td><td>'+pill(o.listing_state,o.listing_state==="メール確認済み"||o.listing_state==="運営確認済み"?"ok":"") + contact+'</td><td>'+e(o.source_type)+'<span class="sub"><a href="'+e(o.source_url)+'" target="_blank" rel="noopener">出典URL</a> / '+e(o.last_checked_at)+'</span></td></tr>'}
    async function load(){filters.q=document.getElementById("orgQ").value;filters.area=document.getElementById("orgArea").value;filters.municipality=document.getElementById("orgMunicipality").value;filters.sort=document.getElementById("orgSort").value;var qs=new URLSearchParams(filters);var rows=await api("/api/organizations?"+qs.toString());document.getElementById("orgCount").textContent=rows.length;document.getElementById("orgRows").innerHTML=rows.map(row).join("")||'<tr><td colspan="8">条件に合う団体はありません。</td></tr>'}
    ["orgQ","orgArea","orgMunicipality","orgSort"].forEach(function(id){document.getElementById(id).addEventListener("input",load);document.getElementById(id).addEventListener("change",load)});
    var pop=document.getElementById("filterPopover"),sel=document.getElementById("filterSelect"),title=document.getElementById("filterTitle");
    document.querySelectorAll("[data-filter]").forEach(function(b){b.onclick=function(ev){ev.stopPropagation();var c=configs[b.dataset.filter];title.textContent=c.title;pop.style.left=Math.min(window.innerWidth-250,b.getBoundingClientRect().left)+"px";pop.style.top=(b.getBoundingClientRect().bottom+5)+"px";pop.classList.add("open");if(c.input){pop.innerHTML='<h3>'+c.title+'</h3><input id="popInput" value="'+e(filters[c.key]||"")+'" placeholder="検索"><button class="btn btn-green" style="margin-top:8px;width:100%" id="popApply">適用</button>';document.getElementById("popApply").onclick=function(){filters[c.key]=document.getElementById("popInput").value;document.getElementById("orgQ").value=filters[c.key];pop.classList.remove("open");load()}}else{pop.innerHTML='<h3>'+c.title+'</h3><select id="popSelect">'+c.values.map(function(v){return '<option value="'+e(v)+'" '+(filters[c.key]===v?"selected":"")+'>'+e(v||"指定なし")+'</option>'}).join("")+'</select>';document.getElementById("popSelect").onchange=function(){filters[c.key]=this.value;if(c.key==="area")document.getElementById("orgArea").value=this.value;pop.classList.remove("open");load()}}}});
    document.addEventListener("click",function(){pop.classList.remove("open")});load().catch(function(){document.getElementById("orgRows").innerHTML='<tr><td colspan="8">団体情報を取得できませんでした。</td></tr>'});
    </script>
    """
    return base_page("団体DB", "organizations", body, script)


def organization_page(profile_slug: str) -> str:
    org = get_organization(profile_slug)
    if not org:
        return base_page("団体が見つかりません", "organizations", '<main class="shell legal"><h1>団体ページが見つかりません</h1><p>公開状態の団体DBに該当するページがありません。</p><a class="btn btn-primary" href="/organizations">団体DBに戻る</a></main>')
    with db() as conn:
        posts = [dict(r) for r in conn.execute(
            "select * from recruitments where organization_id=? and status='open' order by starts_at",
            (org["organization_id"],),
        ).fetchall()]
    contact = ""
    if org.get("public_contact_email"):
        subject = "Pickle Match Kantoを見てご連絡しました。"
        body = "Pickle Match Kantoを見てご連絡しました。%0D%0A%0D%0A希望する内容：%0D%0A希望日時・場所：%0D%0A参加人数：%0D%0Aレベル：%0D%0A補足：%0D%0A"
        contact = (
            '<div class="contact-panel"><h2>連絡を取るならこちら</h2><p>団体代表者が公開に同意した連絡用メールだけを掲載しています。</p>'
            '<a class="btn btn-primary" href="mailto:' + esc(org["public_contact_email"]) + '?subject=' + subject + '&body=' + body + '">メールを作成</a>'
            '<a class="btn btn-outline" href="' + esc(org["official_url"]) + '" target="_blank" rel="noopener">公式サイトを見る</a></div>'
        )
    else:
        contact = (
            '<div class="contact-private"><b>公開連絡先は未登録です。</b><br>代表者の個人メールや氏名は公開しません。公式サイト・公開SNSまたは掲載元の問い合わせ先を利用してください。</div>'
        )
    post_html = ""
    if posts:
        post_html = '<div class="recruitment-list">' + "".join(
            '<article class="recruitment-row"><div class="datebox"><b>' + esc(p["starts_at"].replace("-", "/")) + '</b><span>' + esc(p["weekday_label"]) + "</span></div>"
            '<div><h3 class="listing-title">' + esc(p["title"]) + '</h3><div class="listing-meta"><span>' + esc(p["recruitment_type"]) + "</span><span>" + esc(p["level_label"]) + "</span></div></div>"
            '<div class="listing-side"><a href="' + esc(p["source_url"]) + '" target="_blank" rel="noopener">出典を見る</a></div></article>'
            for p in posts
        ) + "</div>"
    else:
        post_html = '<div class="empty">現在公開中の募集はありません。練習会・イベントの最新情報は掲載元の公式案内で確認してください。</div>'
    body = (
        '<main><section class="profile-header"><div class="shell"><div class="crumb"><a href="/organizations">団体DB</a> / '
        + esc(org["area_group"]) + " / " + esc(org["municipality"]) + '</div><div class="profile-kicker">'
        + '<span class="pill ok">' + esc(org["listing_state"]) + '</span><span class="pill blue">' + esc(org["organization_type"]) + "</span></div>"
        + "<h1>" + esc(org["organization_name"]) + '</h1><p class="profile-lead">' + esc(org["introduction"]) + "</p></div></section>"
        + '<div class="shell profile-grid"><section><div class="profile-section"><h2>活動情報</h2><dl class="detail-list">'
        + "<div><dt>活動エリア</dt><dd>" + esc(org["area_group"]) + " / " + esc(org["municipality"]) + "</dd></div>"
        + "<div><dt>主な会場</dt><dd>" + esc(org["primary_venue"]) + "</dd></div>"
        + "<div><dt>レベル</dt><dd>" + esc(org["level_label"]) + "</dd></div>"
        + "<div><dt>人数</dt><dd>" + esc(org["member_count"]) + "</dd></div>"
        + "<div><dt>雰囲気</dt><dd>" + esc(org["atmosphere"]) + "</dd></div>"
        + "<div><dt>経験者割合</dt><dd>" + esc(org["experience_ratio"]) + "</dd></div>"
        + "<div><dt>練習頻度</dt><dd>" + esc(org["practice_frequency"]) + "</dd></div>"
        + "<div><dt>初心者歓迎</dt><dd>" + ("歓迎" if org["beginner_welcome"] else "経験者向け") + "</dd></div></dl></div>"
        + '<div class="profile-section"><h2>代表コメント</h2><p>' + esc(org["representative_comment"] or "代表者からの公開コメントはまだ登録されていません。") + "</p></div>"
        + '<div class="profile-section"><h2>現在の募集</h2>' + post_html + "</div></section>"
        + '<aside><div class="sidepanel"><h2>掲載情報</h2><p><b>登録状態:</b> ' + esc(org["listing_state"]) + '</p><p><b>出典:</b> ' + esc(org["source_type"]) + '</p><p><b>最終確認日:</b> ' + esc(org["last_checked_at"]) + '</p><a href="' + esc(org["source_url"]) + '" target="_blank" rel="noopener">出典URLを開く</a></div><br>' + contact + '</aside></div></main>'
    )
    return base_page(org["organization_name"], "organizations", body)


def representative_page() -> str:
    body = """
    <main><section class="page-hero"><div class="shell"><div class="crumb">Pickle Match Tokyo / 団体代表者登録</div><h1>団体代表者登録</h1><p>団体情報の新規掲載、掲載修正、公開連絡先の登録を申請できます。一般閲覧にログインは必要ありません。</p></div></section>
    <div class="shell form-layout"><div class="form-intro">代表者名・代表者メール・内部メモは、運営確認のためだけに保存します。公開一覧や公開APIには含めません。公開連絡用メールは、掲載への同意がある場合に限り公開対象です。</div>
      <form id="representativeForm"><div class="form-grid">
        <div class="field span-2"><label>団体名 *</label><input name="organization_name" required></div>
        <div class="field"><label>エリア *</label><select name="area_group" required>""" + option_tags(list(AREA_OPTIONS.keys()), "選択してください") + """</select></div>
        <div class="field"><label>区・市 *</label><select name="municipality" required>""" + municipality_options() + """</select></div>
        <div class="field span-2"><label>主な会場</label><input name="primary_venue" placeholder="例: 渋谷区スポーツセンター"></div>
        <div class="field"><label>レベル</label><select name="level_label">""" + option_tags(LEVELS, "選択してください") + """</select></div>
        <div class="field"><label>団体種別</label><select name="organization_type">""" + option_tags(["地域協会", "地域クラブ", "総合型地域スポーツクラブ", "学生団体", "スクール・施設運営", "その他"], "選択してください") + """</select></div>
        <div class="field"><label>練習頻度</label><input name="practice_frequency" placeholder="例: 毎週土曜"></div>
        <div class="field"><label>人数</label><input name="member_count" placeholder="例: 20〜30名"></div>
        <div class="field span-2"><label>雰囲気</label><input name="atmosphere" placeholder="例: 初心者の参加が多い、ゲーム中心"></div>
        <div class="field span-2"><label>紹介文</label><textarea name="introduction"></textarea></div>
        <div class="field span-2"><label>公式サイトまたは公式SNS</label><input type="url" name="official_url" placeholder="https://"></div>
        <div class="field"><label>代表者名（非公開） *</label><input name="representative_name" required></div>
        <div class="field"><label>代表者メール（非公開） *</label><input type="email" name="representative_email" required></div>
        <div class="field span-2"><label>公開連絡用メール</label><input type="email" name="public_contact_email" placeholder="公開に同意した団体用アドレスのみ"></div>
        <div class="field span-2"><label><input type="checkbox" name="public_contact_consent"> 公開連絡用メールを団体ページで公開することに同意します</label></div>
        <div class="field span-2"><label>本人確認・出典URL</label><input type="url" name="evidence_url" placeholder="公式サイト、公式SNS、団体の掲載根拠など"></div>
        <div class="field span-2"><label><input type="checkbox" name="beginner_welcome"> 初心者を歓迎する</label></div>
      </div><div class="form-actions"><button class="btn btn-primary" type="submit">代表者申請を送信</button></div><div class="form-result" id="representativeResult"></div></form>
    </div></main>
    """
    script = r"""
    <script>
    async function post(path,data){var r=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});var j=await r.json();if(!r.ok)throw new Error(j.error||"送信に失敗しました");return j}
    document.getElementById("representativeForm").onsubmit=async function(x){x.preventDefault();var f=new FormData(x.target),data=Object.fromEntries(f.entries());data.public_contact_consent=f.get("public_contact_consent")==="on";data.beginner_welcome=f.get("beginner_welcome")==="on";var out=document.getElementById("representativeResult");out.style.display="block";out.className="form-result";out.textContent="送信しています。";try{var j=await post("/api/representatives",data);out.textContent="代表者申請を受け付けました。申請番号: "+j.application_id+"。運営確認後に掲載状態を更新します。";x.target.reset()}catch(err){out.className="form-result error";out.textContent=err.message}}
    </script>
    """
    return base_page("団体代表者登録", "representative", body, script)


def post_recruitment_page() -> str:
    body = """
    <main><section class="page-hero"><div class="shell"><div class="crumb">Pickle Match Tokyo / 募集投稿</div><h1>募集を投稿する</h1><p>練習試合、合同練習、初心者向け練習会、交流イベント、メンバー募集、単発参加者募集を申請できます。</p></div></section>
    <div class="shell form-layout"><div class="form-intro">投稿は受付後に内容・出典・公開連絡方法を確認します。運営確認前の投稿を「公式」「認定済み」と表示することはありません。</div>
      <form id="recruitmentForm"><div class="form-grid">
        <div class="field span-2"><label>団体名または主催者名 *</label><input name="organization_name" required></div>
        <div class="field span-2"><label>募集タイトル *</label><input name="title" required placeholder="例: 土曜午後の合同練習 相手募集"></div>
        <div class="field"><label>募集種別 *</label><select name="recruitment_type" required>""" + option_tags(RECRUITMENT_TYPES, "選択してください") + """</select></div>
        <div class="field"><label>レベル *</label><select name="level_label" required>""" + option_tags(LEVELS, "選択してください") + """</select></div>
        <div class="field"><label>開催日・募集開始 *</label><input type="datetime-local" name="starts_at" required></div>
        <div class="field"><label>終了日時・募集締切</label><input type="datetime-local" name="ends_at"></div>
        <div class="field"><label>エリア *</label><select name="area_group" required>""" + option_tags(list(AREA_OPTIONS.keys()), "選択してください") + """</select></div>
        <div class="field"><label>区・市 *</label><select name="municipality" required>""" + municipality_options() + """</select></div>
        <div class="field"><label>会場名</label><input name="venue_name"></div>
        <div class="field"><label>屋内・屋外</label><select name="venue_type"><option value="">選択してください</option><option>屋内</option><option>屋外</option></select></div>
        <div class="field"><label>参加費</label><input name="fee_label" placeholder="例: 1,500円"></div>
        <div class="field"><label>募集人数</label><input name="capacity_label" placeholder="例: 8名"></div>
        <div class="field"><label>年齢層の目安</label><input name="age_guidance" placeholder="例: 20代〜40代中心"></div>
        <div class="field"><label>時間帯</label><select name="time_band">""" + option_tags(TIME_BANDS, "選択してください") + """</select></div>
        <div class="field span-2"><label>補足・条件</label><textarea name="notes"></textarea></div>
        <div class="field span-2"><label>連絡方法 *</label><input name="contact_method" required placeholder="例: 公式フォーム、公開メール、DM"></div>
        <div class="field span-2"><label>出典URLまたは団体の公式URL *</label><input type="url" name="source_url" required placeholder="https://"></div>
        <div class="field span-2"><label><input type="checkbox" name="beginner_welcome"> 初心者歓迎</label></div>
      </div><div class="form-actions"><button class="btn btn-primary" type="submit">募集投稿を申請</button></div><div class="form-result" id="recruitmentResult"></div></form>
    </div></main>
    """
    script = r"""
    <script>
    async function post(path,data){var r=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});var j=await r.json();if(!r.ok)throw new Error(j.error||"送信に失敗しました");return j}
    document.getElementById("recruitmentForm").onsubmit=async function(x){x.preventDefault();var f=new FormData(x.target),data=Object.fromEntries(f.entries());data.beginner_welcome=f.get("beginner_welcome")==="on";var out=document.getElementById("recruitmentResult");out.style.display="block";out.className="form-result";out.textContent="送信しています。";try{var j=await post("/api/recruitments",data);out.textContent="募集投稿を受け付けました。受付番号: "+j.recruitment_id+"。確認後に募集掲示板へ掲載します。";x.target.reset()}catch(err){out.className="form-result error";out.textContent=err.message}}
    </script>
    """
    return base_page("募集投稿", "representative", body, script)


def operator_page() -> str:
    body = """
    <main class="shell legal"><div class="crumb">Pickle Match Tokyo / 運営者情報</div><h1>運営者情報</h1>
    <p>Pickle Match Tokyoは、東京都内のピックルボール団体・練習会・プレイヤーをつなぐ情報検索と募集掲載のサービスです。</p>
    <h2>運営窓口</h2><p>名称: Pickle Match Tokyo 運営事務局<br>連絡方法: <a href="/contact">お問い合わせフォーム</a><br>対応内容: 掲載申請、掲載修正、削除依頼、なりすまし・虚偽申請の通報、サービスに関する問い合わせ</p>
    <h2>運営方針</h2><p>団体代表者からの更新情報と、出典・最終確認日を伴う公開情報を中心に扱います。公開前の候補情報は公開DBへ自動掲載せず、運営確認または団体申請を経て掲載します。</p>
    <h2>広告について</h2><p>初期版では広告を掲載していません。将来広告を導入する場合も、検索・比較・募集という利用者向け機能を主目的として運営し、広告であることを明確に表示します。</p>
    </main>
    """
    return base_page("運営者情報", "", body)


def privacy_page() -> str:
    body = """
    <main class="shell legal"><div class="crumb">Pickle Match Tokyo / プライバシーポリシー</div><h1>プライバシーポリシー</h1>
    <p>Pickle Match Tokyo 運営事務局は、サービス運営に必要な範囲で個人情報を取り扱います。</p>
    <h2>取得する情報</h2><ul><li>団体代表者登録: 代表者名、代表者メール、団体情報、本人確認のための出典URL</li><li>募集投稿: 投稿者が入力した団体名、募集内容、連絡方法、出典URL</li><li>問い合わせ・通報: 氏名またはハンドルネーム、メール、内容</li></ul>
    <h2>利用目的</h2><p>掲載内容の確認、申請者との連絡、なりすまし・虚偽申請の防止、問い合わせ対応、サービス改善のために利用します。</p>
    <h2>公開情報と非公開情報の分離</h2><p>代表者個人の氏名・メール・内部メモは公開一覧、団体詳細、公開APIに含めません。公開連絡用メールは、団体代表者が公開に同意したアドレスだけを公開します。</p>
    <h2>第三者提供</h2><p>法令に基づく場合を除き、本人の同意なく個人情報を第三者に提供しません。</p>
    <h2>開示・訂正・削除</h2><p>保有情報の開示、訂正、削除を希望する場合は、<a href="/contact">お問い合わせフォーム</a>から連絡してください。本人確認を行ったうえで合理的な期間内に対応します。</p>
    </main>
    """
    return base_page("プライバシーポリシー", "", body)


def terms_page() -> str:
    body = """
    <main class="shell legal"><div class="crumb">Pickle Match Tokyo / 利用規約</div><h1>利用規約</h1>
    <p>この規約は、Pickle Match Tokyoの閲覧、団体代表者登録、募集投稿、問い合わせに適用します。</p>
    <h2>掲載情報</h2><p>本サービスは公開情報・団体申請をもとに情報を掲載します。開催の有無、参加条件、費用、募集状況の正確性を保証するものではなく、利用者は出典・主催者案内で最終確認を行うものとします。</p>
    <h2>禁止事項</h2><ul><li>虚偽の団体情報、なりすまし、権利侵害情報の投稿</li><li>営利目的の無関係な勧誘、迷惑行為、差別・ハラスメント</li><li>他者の個人情報を本人の同意なく掲載する行為</li><li>サービスの運営を妨害する行為</li></ul>
    <h2>掲載の停止・削除</h2><p>規約違反、権利侵害のおそれ、内容の不正確さ、または運営上の必要があると判断した場合、事前通知なく掲載を停止・削除することがあります。</p>
    <h2>免責</h2><p>利用者間または主催者との間で発生したトラブルについて、運営事務局は責任を負いません。安全配慮、施設規約、保険、参加費の支払いなどは各参加者・主催者の責任で確認してください。</p>
    </main>
    """
    return base_page("利用規約", "", body)


def about_data_page() -> str:
    body = """
    <main class="shell legal"><div class="crumb">Pickle Match Tokyo / 掲載情報・訂正削除方針</div><h1>掲載情報・訂正削除方針</h1>
    <p>団体DBは、東京都内のピックルボール活動を探しやすくするための検索・比較データベースです。イベント名、試合結果、記事タイトル、個人名、単なる会場情報は団体DBへ混在させません。</p>
    <h2>情報源と掲載基準</h2><ul><li>団体の公式Webサイト、公式SNS、または団体代表者からの申請を出典にします。</li><li>公開ページには出典URLと最終確認日を保存・表示します。</li><li>根拠が不足する候補は候補DBに留め、公開DBへ自動掲載しません。</li><li>運営確認前の団体を「公式」「認定済み」と表現しません。</li></ul>
    <h2>登録状態</h2><ul><li>公開情報確認済み: 出典URLと最終確認日を運営が確認した状態</li><li>代表申請受付: 団体代表者からの申請を受領した状態</li><li>運営確認済み: 掲載内容の運営確認を完了した状態</li><li>メール確認済み: 公開連絡用メールの確認を完了した状態</li></ul>
    <h2>訂正・削除・通報</h2><p>本人・団体代表者・権利者は、掲載情報の訂正・削除を依頼できます。なりすまし、虚偽申請、連絡先の不正掲載は、根拠URLや状況を添えて<a href="/contact">お問い合わせフォーム</a>から通報してください。内容を確認し、必要に応じて非公開化・訂正・削除します。</p>
    </main>
    """
    return base_page("掲載情報・訂正削除方針", "", body)


def contact_page() -> str:
    email_panel, email_script = contact_panel(SITE_NAME, CONTACT_EMAIL)
    body = """
    <main><section class="page-hero"><div class="shell"><div class="crumb">Pickle Match Tokyo / 問い合わせ</div><h1>問い合わせ</h1><p>掲載申請、訂正・削除依頼、なりすまし・虚偽申請の通報、一般的な問い合わせを受け付けます。</p></div></section>
    """ + email_panel + """
    <div class="shell form-layout"><h2>サイト内の受付窓口</h2><p>内容は運営者の受付一覧に保存されます。メールは送信されません。メールでの連絡をご希望の場合は上の窓口をご利用ください。</p><form id="contactForm"><div class="form-grid">
      <div class="field"><label>お名前</label><input name="name"></div><div class="field"><label>メールアドレス *</label><input type="email" name="email" required></div>
      <div class="field span-2"><label>お問い合わせ種別 *</label><select name="category" required><option value="">選択してください</option><option>掲載情報の訂正</option><option>掲載情報の削除依頼</option><option>なりすまし・虚偽申請の通報</option><option>団体代表者登録</option><option>その他</option></select></div>
      <div class="field span-2"><label>内容 *</label><textarea name="message" required placeholder="対象団体名、該当URL、訂正内容などを記載してください。"></textarea></div>
    </div><div class="form-actions"><button class="btn btn-primary" type="submit">送信する</button></div><div class="form-result" id="contactResult"></div></form></div></main>
    """
    script = r"""
    <script>
    async function post(path,data){var r=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});var j=await r.json();if(!r.ok)throw new Error(j.error||"送信に失敗しました");return j}
    document.getElementById("contactForm").onsubmit=async function(x){x.preventDefault();var out=document.getElementById("contactResult");out.style.display="block";out.textContent="受付へ保存しています。";try{var j=await post("/api/contact",Object.fromEntries(new FormData(x.target).entries()));out.className="form-result";out.textContent="サイト内で受け付けました。受付番号: "+j.contact_id;x.target.reset()}catch(err){out.className="form-result error";out.textContent=err.message}}
    </script>
    """
    return base_page("問い合わせ", "", body, script + email_script)


def robots_txt() -> str:
    return "User-agent: *\nAllow: /\nDisallow: /api/\nSitemap: /sitemap.xml\n"


def sitemap_xml() -> str:
    urls = ["/", "/recruitments", "/organizations", "/representative", "/post-recruitment", "/operator", "/privacy", "/terms", "/about-data", "/contact"]
    urls.extend("/organizations/" + item["profile_slug"] for item in list_organizations({}))
    return "<?xml version=\"1.0\" encoding=\"UTF-8\"?><urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">" + "".join("<url><loc>" + esc(SITE_BASE_URL) + u + "</loc></url>" for u in urls) + "</urlset>"


class Handler(BaseHTTPRequestHandler):
    server_version = "PickleMatchKanto/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        print("%s - %s" % (self.address_string(), fmt % args))

    def send_bytes(self, data: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store" if content_type.startswith("application/json") else "public, max-age=300")
        self.end_headers()
        self.wfile.write(data)

    def send_html(self, content: str, status: int = 200) -> None:
        self.send_bytes(content.encode("utf-8"), "text/html; charset=utf-8", status)

    def send_json(self, obj: object, status: int = 200) -> None:
        self.send_bytes(json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", status)

    def send_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_html("<h1>Not Found</h1>", 404)
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_bytes(path.read_bytes(), content_type)

    def read_json(self) -> dict:
        size = int(self.headers.get("Content-Length", "0"))
        if size <= 0 or size > 200_000:
            raise ValueError("送信内容が不正です。")
        return json.loads(self.rfile.read(size).decode("utf-8"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/":
                self.send_html(home_page())
            elif parsed.path == "/recruitments":
                self.send_html(recruitment_page())
            elif parsed.path == "/organizations":
                self.send_html(organizations_page())
            elif parsed.path.startswith("/organizations/"):
                self.send_html(organization_page(unquote(parsed.path.rsplit("/", 1)[-1])))
            elif parsed.path == "/representative":
                self.send_html(representative_page())
            elif parsed.path == "/post-recruitment":
                self.send_html(post_recruitment_page())
            elif parsed.path == "/operator":
                self.send_html(operator_page())
            elif parsed.path == "/privacy":
                self.send_html(privacy_page())
            elif parsed.path == "/terms":
                self.send_html(terms_page())
            elif parsed.path == "/about-data":
                self.send_html(about_data_page())
            elif parsed.path == "/contact":
                self.send_html(contact_page())
            elif parsed.path == "/assets/hero-pickleball.png":
                self.send_file(ROOT / "assets" / "hero-pickleball.png")
            elif parsed.path == "/healthz":
                self.send_json({"ok": True, "db": str(DB_PATH), **summary()})
            elif parsed.path == "/robots.txt":
                self.send_bytes(robots_txt().encode("utf-8"), "text/plain; charset=utf-8")
            elif parsed.path == "/sitemap.xml":
                self.send_bytes(sitemap_xml().encode("utf-8"), "application/xml; charset=utf-8")
            elif parsed.path == "/api/summary":
                self.send_json(summary())
            elif parsed.path == "/api/organizations":
                self.send_json(list_organizations(parse_qs(parsed.query)))
            elif parsed.path == "/api/recruitments":
                self.send_json(list_recruitments(parse_qs(parsed.query)))
            elif parsed.path == "/api/areas":
                self.send_json(AREA_OPTIONS)
            else:
                self.send_html("<h1>Not Found</h1>", 404)
        except Exception as exc:
            traceback.print_exc()
            self.send_json({"error": str(exc)}, 500)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            data = self.read_json()
            if parsed.path == "/api/representatives":
                self.create_representative(data)
            elif parsed.path == "/api/recruitments":
                self.create_recruitment(data)
            elif parsed.path == "/api/contact":
                self.create_contact(data)
            elif parsed.path == "/api/reports":
                self.create_report(data)
            else:
                self.send_json({"error": "Not Found"}, 404)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, 400)
        except Exception as exc:
            traceback.print_exc()
            self.send_json({"error": "送信処理に失敗しました。"}, 500)

    def create_representative(self, data: dict) -> None:
        required = ["organization_name", "area_group", "municipality", "representative_name", "representative_email"]
        if any(not str(data.get(k, "")).strip() for k in required):
            raise ValueError("必須項目を入力してください。")
        public_email = str(data.get("public_contact_email", "")).strip()
        consent = bool(data.get("public_contact_consent"))
        if public_email and not consent:
            raise ValueError("公開連絡用メールを入力する場合は、公開への同意が必要です。")
        if consent and not public_email:
            raise ValueError("公開に同意するメールアドレスを入力してください。")
        application_id = "rep-" + uuid.uuid4().hex[:10]
        with db() as conn:
            conn.execute(
                """
                insert into representative_applications (
                  application_id, organization_name, area_group, municipality, primary_venue,
                  level_label, organization_type, practice_frequency, member_count, atmosphere,
                  beginner_welcome, introduction, official_url, representative_name,
                  representative_email, public_contact_email, public_contact_consent,
                  evidence_url, internal_memo, status, received_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', 'pending', ?)
                """,
                (
                    application_id, data["organization_name"].strip(), data["area_group"], data["municipality"],
                    data.get("primary_venue", "").strip(), data.get("level_label", ""), data.get("organization_type", ""),
                    data.get("practice_frequency", "").strip(), data.get("member_count", "").strip(),
                    data.get("atmosphere", "").strip(), int(bool(data.get("beginner_welcome"))),
                    data.get("introduction", "").strip(), data.get("official_url", "").strip(),
                    data["representative_name"].strip(), data["representative_email"].strip(),
                    public_email, int(consent), data.get("evidence_url", "").strip(), now_iso(),
                ),
            )
        self.send_json({"ok": True, "application_id": application_id})

    def create_recruitment(self, data: dict) -> None:
        required = ["organization_name", "title", "recruitment_type", "level_label", "starts_at", "area_group", "municipality", "contact_method", "source_url"]
        if any(not str(data.get(k, "")).strip() for k in required):
            raise ValueError("必須項目を入力してください。")
        recruitment_id = "pending-" + uuid.uuid4().hex[:10]
        starts_at = data["starts_at"].replace("T", " ")
        ends_at = data.get("ends_at", "").replace("T", " ")
        with db() as conn:
            conn.execute(
                """
                insert into recruitments (
                  recruitment_id, organization_name, title, recruitment_type, level_label,
                  starts_at, ends_at, area_group, municipality, venue_name, venue_type,
                  fee_label, fee_amount, capacity_label, beginner_welcome, age_guidance,
                  time_band, weekday_label, notes, contact_method, source_type, source_url,
                  listing_state, status, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, '', ?, ?, '団体代表者申請', ?, '代表申請受付', 'pending', ?, ?)
                """,
                (
                    recruitment_id, data["organization_name"].strip(), data["title"].strip(), data["recruitment_type"],
                    data["level_label"], starts_at, ends_at, data["area_group"], data["municipality"],
                    data.get("venue_name", "").strip(), data.get("venue_type", ""), data.get("fee_label", "").strip(),
                    data.get("capacity_label", "").strip(), int(bool(data.get("beginner_welcome"))),
                    data.get("age_guidance", "").strip(), data.get("time_band", ""), data.get("notes", "").strip(),
                    data["contact_method"].strip(), data["source_url"].strip(), now_iso(), now_iso(),
                ),
            )
        self.send_json({"ok": True, "recruitment_id": recruitment_id})

    def create_contact(self, data: dict) -> None:
        if not str(data.get("email", "")).strip() or not str(data.get("category", "")).strip() or not str(data.get("message", "")).strip():
            raise ValueError("メールアドレス、お問い合わせ種別、内容を入力してください。")
        contact_id = "contact-" + uuid.uuid4().hex[:10]
        with db() as conn:
            conn.execute(
                "insert into contact_requests (contact_id, name, email, category, message, received_at) values (?, ?, ?, ?, ?, ?)",
                (contact_id, data.get("name", "").strip(), data["email"].strip(), data["category"].strip(), data["message"].strip(), now_iso()),
            )
        self.send_json({"ok": True, "contact_id": contact_id})

    def create_report(self, data: dict) -> None:
        if not str(data.get("report_type", "")).strip() or not str(data.get("detail", "")).strip():
            raise ValueError("通報種別と内容を入力してください。")
        report_id = "report-" + uuid.uuid4().hex[:10]
        with db() as conn:
            conn.execute(
                "insert into reports (report_id, report_type, target_name, reporter_email, detail, received_at) values (?, ?, ?, ?, ?, ?)",
                (report_id, data["report_type"], data.get("target_name", ""), data.get("reporter_email", ""), data["detail"], now_iso()),
            )
        self.send_json({"ok": True, "report_id": report_id})


def main() -> None:
    init_db()
    if len(sys.argv) > 1 and sys.argv[1] == "--init-only":
        print(json.dumps({"db": str(DB_PATH), **summary()}, ensure_ascii=False, indent=2))
        return
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("%s: http://%s:%s" % (SITE_NAME, HOST, PORT))
    print("SQLite DB: %s" % DB_PATH)
    server.serve_forever()


if __name__ == "__main__":
    main()
