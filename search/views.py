import json
import pickle
import re
import redis
from django.shortcuts import render
from django.views.generic.base import View
from django.http import HttpResponse
from datetime import datetime
from w3lib.html import remove_tags
from elasticsearch import Elasticsearch
from search.models import ArticleType, LagouType, ZhiHuQuestionType, ZhiHuAnswerType
from django.views.generic.base import RedirectView
from utils.common import OrderedSet


client = Elasticsearch(hosts=['127.0.0.1'])

redis_cli = redis.StrictRedis()


class IndexView(View):
    def get(self, request):
        topn_search_clean = []
        topn_search = redis_cli.zrevrangebyscore(
            "search_keywords_set", "+inf", "-inf", start=0, num=5)
        for topn_key in topn_search:
            topn_key = str(topn_key, encoding="utf-8")
            topn_search_clean.append(topn_key)
        topn_search = topn_search_clean
        return render(request, "index.html", {"topn_search": topn_search})


class SearchSuggest(View):

    def get(self, request):
        key_words = request.GET.get('s', '')
        current_page = request.GET.get('s_type', '')
        if current_page == "article":
            re_datas = []
            if key_words:
                s = ArticleType.search()
                s = s.suggest('my_suggest', key_words, completion={
                    "field": "suggest", "fuzzy": {
                        "fuzziness": 2
                    },
                    "size": 10
                })
                suggestions = s.execute_suggest()
                for match in suggestions.my_suggest[0].options[:10]:
                    source = match._source
                    re_datas.append(source["title"])
            return HttpResponse(json.dumps(re_datas), content_type="application/json")
        elif current_page == "job":
            re_datas = []
            if key_words:
                s = LagouType.search()
                s = s.suggest('my_suggest', key_words, completion={
                    "field": "suggest", "fuzzy": {
                        "fuzziness": 2
                    },
                    "size": 10
                })
                suggestions = s.execute_suggest()
                name_set = OrderedSet()
                for match in suggestions.my_suggest[0].options[:10]:
                    source = match._source
                    name_set.add(source["title"])
                for name in name_set:
                    re_datas.append(name)
            return HttpResponse(json.dumps(re_datas), content_type="application/json")
        elif current_page == "question":
            re_datas = []
            if key_words:
                s = ZhiHuQuestionType.search()
                s = s.suggest('my_suggest', key_words, completion={
                    "field": "suggest", "fuzzy": {
                        "fuzziness": 2
                    },
                    "size": 10
                })
                name_set = OrderedSet()
                suggestions = s.execute_suggest()
                if suggestions:
                    for match in suggestions.my_suggest[0].options[:10]:
                        if match._type == "question":
                            source = match._source
                            re_datas.append(source["title"])
                        elif match._type == "answer":
                            source = match._source
                            name_set.add(source["author_name"])
                for name in name_set:
                    re_datas.append(name)
            return HttpResponse(json.dumps(re_datas), content_type="application/json")


class SearchView(View):

    def get(self, request):
        key_words = request.GET.get("q", "")

        # 通用部分
        # 实现搜索关键词keyword加1操作
        redis_cli.zincrby("search_keywords_set", key_words)
        # 获取topn个搜索词
        topn_search_clean = []
        topn_search = redis_cli.zrevrangebyscore(
            "search_keywords_set", "+inf", "-inf", start=0, num=5)
        for topn_key in topn_search:
            topn_key = str(topn_key, encoding="utf-8")
            topn_search_clean.append(topn_key)
        topn_search = topn_search_clean
        # 获取伯乐在线的文章数量

        jobbole_count = redis_cli.get("jobbole_count")
        if jobbole_count:
            jobbole_count = int(pickle.loads(pickle.dumps(jobbole_count)))
        else:
            jobbole_count = 0
        job_count = redis_cli.get("job_count")
        if job_count:
            job_count = int(pickle.loads(pickle.dumps(job_count)))
        else:
            job_count = 0
        zhihu_count = redis_cli.get("zhihu_count")
        if zhihu_count:
            zhihu_count = int(pickle.loads(pickle.dumps(zhihu_count)))
        else:
            zhihu_count = 0

        # 当前要获取第几页的数据
        page = request.GET.get("p", "1")
        try:
            page = int(page)
        except BaseException:
            page = 1
        response = []
        start_time = datetime.now()
        s_type = request.GET.get("s_type", "")
        if s_type == "article":
            response = client.search(
                index="jobbole",
                request_timeout=60,
                body={
                    "query": {
                        "multi_match": {
                            "query": key_words,
                            "fields": ["tags", "title", "content"]
                        }
                    },
                    "from": (page - 1) * 10,
                    "size": 10,
                    "highlight": {
                        "pre_tags": ['<span class="keyWord">'],
                        "post_tags": ['</span>'],
                        "fields": {
                            "title": {},
                            "content": {},
                        }
                    }
                }
            )
        elif s_type == "job":
            response = client.search(
                index="lagou",
                request_timeout=60,
                body={
                    "query": {
                        "multi_match": {
                            "query": key_words,
                            "fields": [
                                "title",
                                "tags",
                                "job_desc",
                                "job_advantage",
                                "company_name",
                                "job_addr",
                                "job_city",
                                "degree_need"]}},
                    "from": (
                        page - 1) * 10,
                    "size": 10,
                    "highlight": {
                        "pre_tags": ['<span class="keyWord">'],
                        "post_tags": ['</span>'],
                        "fields": {
                            "title": {},
                            "job_desc": {},
                            "company_name": {},
                        }}})
        elif s_type == "question":
            response = client.search(
                index="zhihu",
                request_timeout=60,
                body={
                    "query": {
                        "multi_match": {
                            "query": key_words,
                            "fields": [
                                "topics",
                                "title",
                                "content",
                                "author_name"]}},
                    "from": (
                        page - 1) * 10,
                    "size": 10,
                    "highlight": {
                        "pre_tags": ['<span class="keyWord">'],
                        "post_tags": ['</span>'],
                        "fields": {
                            "title": {},
                            "content": {},
                            "author_name": {},
                        }}})

        end_time = datetime.now()
        last_seconds = (end_time - start_time).total_seconds()

        # 具体的信息
        hit_list = []
        hit_dict = {}
        error_nums = 0
        if s_type == "article":
            for hit in response["hits"]["hits"]:
                hit_dict = {}
                try:
                    if "title" in hit["highlight"]:
                        hit_dict["title"] = "".join(hit["highlight"]["title"])
                    else:
                        hit_dict["title"] = hit["_source"]["title"]
                    if "content" in hit["highlight"]:
                        hit_dict["content"] = "".join(hit["highlight"]["content"])[:500]
                    else:
                        hit_dict["content"] = hit["_source"]["content"][:500]
                    hit_dict["create_date"] = hit["_source"]["create_date"]
                    hit_dict["url"] = hit["_source"]["url"]
                    hit_dict["score"] = hit["_score"]
                    hit_dict["source_site"] = "伯乐在线"
                    hit_list.append(hit_dict)
                except:
                    error_nums = error_nums + 1
        elif s_type == "job":
            error_nums = 0
            for hit in response["hits"]["hits"]:
                hit_dict = {}
                try:
                    if "title" in hit["highlight"]:
                        hit_dict["title"] = "".join(hit["highlight"]["title"])
                    else:
                        hit_dict["title"] = hit["_source"]["title"]
                    if "job_desc" in hit["highlight"]:
                        hit_dict["content"] = "".join(hit["highlight"]["job_desc"])[:500]
                    else:
                        hit_dict["content"] = hit["_source"]["job_desc"][:500]
                    hit_dict["create_date"] = hit["_source"]["publish_time"]
                    hit_dict["url"] = hit["_source"]["url"]
                    hit_dict["score"] = hit["_score"]
                    hit_dict["company_name"] = hit["_source"]["company_name"]
                    hit_dict["source_site"] = "拉勾网"
                    hit_list.append(hit_dict)
                except:
                    hit_dict["title"] = hit["_source"]["title"]
                    hit_dict["content"] = hit["_source"]["job_desc"]
                    hit_dict["create_date"] = hit["_source"]["publish_time"]
                    hit_dict["url"] = hit["_source"]["url"]
                    hit_dict["score"] = hit["_score"]
                    hit_dict["company_name"] = hit["_source"]["company_name"]
                    hit_dict["source_site"] = "拉勾网"
                    hit_list.append(hit_dict)
        elif s_type == "question":
            error_nums = 0
            for hit in response["hits"]["hits"]:
                hit_dict = {}
                try:
                    if hit["_type"] == "answer":
                        if "author_name" in hit["highlight"]:
                            hit_dict["title"] = "".join(
                                hit["highlight"]["author_name"])
                        else:
                            hit_dict["title"] = hit["_source"]["author_name"]
                        if "content" in hit["highlight"]:
                            hit_dict["content"] = "".join(
                                hit["highlight"]["content"])
                        else:
                            hit_dict["content"] = hit["_source"]["content"]
                        hit_dict["create_date"] = hit["_source"]["update_time"]
                        hit_dict["score"] = hit["_score"]
                        data_url = hit["_source"]["url"]
                        match_url = re.match(".*answers/(\d+)", data_url)
                        question_id = hit["_source"]["question_id"]
                        answer_id = match_url.group(1)
                        hit_dict["url"] = "https://www.zhihu.com/question/{0}/answer/{1}".format(
                            question_id, answer_id)
                        hit_dict["source_site"] = "知乎问答"
                        hit_list.append(hit_dict)
                    elif hit["_type"] == "question":
                        if "title" in hit["highlight"]:
                            hit_dict["title"] = "".join(
                                hit["highlight"]["title"])
                        else:
                            hit_dict["title"] = hit["_source"]["title"]
                        if "content" in hit["highlight"]:
                            hit_dict["content"] = "".join(hit["highlight"]["content"])[:500]
                        else:
                            hit_dict["content"] = hit["_source"]["content"][:500]
                        hit_dict["create_date"] = hit["_source"]["crawl_time"]
                        hit_dict["url"] = hit["_source"]["url"]
                        hit_dict["score"] = hit["_score"]
                        hit_dict["source_site"] = "知乎问答"
                        hit_list.append(hit_dict)
                    else:
                        continue
                except:
                    if hit["_type"] == "answer":
                        hit_dict["title"] = hit["_source"]["author_name"]
                        hit_dict["content"] = hit["_source"]["content"]
                        hit_dict["create_date"] = hit["_source"]["update_time"]
                        hit_dict["score"] = hit["_score"]
                        data_url = hit["_source"]["url"]
                        match_url = re.match(".*answers/(\d+)", data_url)
                        question_id = hit["_source"]["question_id"]
                        answer_id = match_url.group(1)
                        hit_dict["url"] = "https://www.zhihu.com/question/{0}/answer/{1}".format(
                            question_id, answer_id)
                        hit_dict["source_site"] = "知乎问答"
                        hit_list.append(hit_dict)
                    elif hit["_type"] == "question":
                        hit_dict["title"] = hit["_source"]["title"]
                        hit_dict["content"] = hit["_source"]["content"]
                        hit_dict["create_date"] = hit["_source"]["crawl_time"]
                        hit_dict["url"] = hit["_source"]["url"]
                        hit_dict["score"] = hit["_score"]
                        hit_dict["source_site"] = "知乎问答"
                        hit_list.append(hit_dict)
                    else:
                        continue
        total_nums = int(response["hits"]["total"])

        # 计算出总页数
        if (page % 10) > 0:
            page_nums = int(total_nums / 10) + 1
        else:
            page_nums = int(total_nums / 10)
        return render(request, "result.html", {"page": page,
                                               "all_hits": hit_list,
                                               "key_words": key_words,
                                               "total_nums": total_nums,
                                               "page_nums": page_nums,
                                               "last_seconds": last_seconds,
                                               "topn_search": topn_search,
                                               "jobbole_count": jobbole_count,
                                               "s_type": s_type,
                                               "job_count": job_count,
                                               "zhihu_count": zhihu_count,
                                               })


favicon_view = RedirectView.as_view(
    url='http://127.0.0.1:8000/static/favicon.ico', permanent=True)












