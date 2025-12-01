import streamlit as st
import pandas as pd
import re
from datetime import datetime

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np


st.set_page_config(layout="wide")

st.title('PON下光猫掉线分析')
st.divider()






# 输入爬取时间，如'2025-08-19 15:00:00'（将用于替换downtime中的空值）
def convert_time_format(input_str):
    # 使用正则表达式提取日期时间部分
    match = re.search(r'(\d{8})_(\d{2}-\d{2}-\d{2})', input_str)
    if not match:
        raise ValueError("输入字符串格式不正确")

    date_part = match.group(1)
    time_part = match.group(2).replace('-', ':')

    # 解析原始时间
    original_time = datetime.strptime(f"{date_part} {time_part}", "%Y%m%d %H:%M:%S")

    # 转换为目标格式
    return original_time.strftime("%Y-%m-%d %H:%M:%S")






class C600Processor(object):

    def __init__(self, up_down_df):
        self.null_time_str = '0000-00-00 00:00:00'
        self.up_down_df = self.process_up_down_df(up_down_df)
        self.all_onusn_set = set(up_down_df["onusn"])
        self.all_onuid_set = set(up_down_df["onuid"])

    def standard_downtime(self, col):
        if col == self.null_time_str:
            return DOWNTIME_ENDTIME
        else:
            return col

    def get_onu_label(self, row):
        return f"{row['current_speed_mode']} {row['onuid']} {row['onusn']}"

    def process_up_down_df(self, up_down_df):
        # uptime
        up_down_df = up_down_df.drop(up_down_df[up_down_df['uptime'] == self.null_time_str].index)
        up_down_df['uptime'] = pd.to_datetime(up_down_df['uptime'])
        # downtime
        up_down_df['downtime'] = pd.to_datetime(up_down_df['downtime'].apply(self.standard_downtime))
        # cause
        up_down_df['cause'] = up_down_df['cause'].fillna("-")

        # label
        up_down_df['onu'] = up_down_df.apply(self.get_onu_label, axis=1)
        up_down_df = up_down_df.sort_values('onu')

        return up_down_df


    def plot_up_down_df_timeline(self):
        up_down_df_show = self.up_down_df
        # up_down_df_show = up_down_df[up_down_df['cause']!='DyingGasp']

        fig = px.timeline(up_down_df_show, x_start="uptime", x_end="downtime", y="onu", color='cause',
                          hover_data=['cause', 'current_speed_mode', 'time_ind'])  # , facet_row='current_speed_mode')

        fig.update_layout(yaxis=dict(
            fixedrange=True
        ))
        

        fig.update_layout(width=1500, height=1200)

        fig.update_xaxes(rangeslider_visible=True)

        st.plotly_chart(fig)

        # plotly.offline.iplot(fig)
        # config={'scrollZoom': True}

        # HTML(fig.to_html())

    def get_los_dying_count(self, row):
        dying_num = 0
        losi_num = 0
        dying_onuid_list = []
        losi_onuid_list = []
        dying_onusn_list = []
        losi_onusn_list = []

        # print(row['cause'])
        for i in range(len(row["cause"])):
            try:
                if "DyingGasp" in row["cause"][i]:

                    dying_num += 1
                    dying_onuid_list.append(row["onuid"][i])
                    dying_onusn_list.append(row["onusn"][i])

                elif "LO" in row["cause"][i]:
                    losi_num += 1
                    losi_onuid_list.append(row["onuid"][i])
                    losi_onusn_list.append(row["onusn"][i])
            except:
                pass
                # print(row["cause"])

        return losi_num, dying_num, losi_onuid_list, losi_onusn_list, dying_onuid_list, dying_onusn_list

    def get_not_included_onu(self, row):

        not_inc_onusn_set = self.all_onusn_set - set(row["onusn"])
        not_inc_onuid_set = self.all_onuid_set - set(row["onuid"])
        not_inc_onu_num = len(not_inc_onusn_set)
        return not_inc_onu_num, list(not_inc_onusn_set), list(not_inc_onuid_set)

    def get_time_groupby_df(self, groupby_col):
        time_groupby_df = self.up_down_df.sort_values("downtime").groupby(groupby_col)[["onuid", "onusn", "cause"]].agg(list)
        # print("down时间点")

        time_groupby_df["总掉线次数"] = time_groupby_df["onusn"].apply(lambda x: len(x))
        time_groupby_df["总掉线ONU个数"] = time_groupby_df["onusn"].apply(lambda x: len(set(x)))

        time_groupby_df["losi次数"], time_groupby_df["dying-gasp次数"], time_groupby_df[
            "losi_onuid_list"], \
            time_groupby_df["losi_onusn_list"], time_groupby_df["dying_onuid_list"], time_groupby_df[
            "dying_onusn_list"] = zip(*time_groupby_df.apply(self.get_los_dying_count, axis=1))

        # 这段时间内没有上线记录的ONU，标出
        time_groupby_df['not_inc_onu_num'], time_groupby_df['not_inc_onusn_set'], time_groupby_df[
            'not_inc_onuid_set'] = zip(
            *time_groupby_df.apply(self.get_not_included_onu, axis=1))
        time_groupby_df = time_groupby_df.sort_values("losi次数", ascending=False)


        fig = px.line(time_groupby_df.reset_index().sort_values(groupby_col),
                      x=groupby_col, y="losi次数",
                      hover_data=["losi_onuid_list", "not_inc_onuid_set"])
        fig.update_xaxes(rangeslider_visible=True,
                         rangeselector=dict(
                             buttons=list([
                                 dict(count=1, label="1m", step="month", stepmode="backward"),
                                 dict(count=6, label="6m", step="month", stepmode="backward"),
                                 dict(count=1, label="YTD", step="year", stepmode="todate"),
                                 dict(count=1, label="1y", step="year", stepmode="backward"),
                                 dict(step="all")
                             ])
                         )

                         )

        st.dataframe(time_groupby_df)
        st.plotly_chart(fig)

        return time_groupby_df




    def analyze_time(self):
        onu_num = len(self.all_onusn_set)

        st.success(f"pon下共{onu_num}个onu")

        # s, min, h聚合
        # 华为的有+08:00
        self.up_down_df['downtime_min'] = self.up_down_df['downtime'].apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S")[:-3]+':00')
        self.up_down_df['downtime_10min'] = self.up_down_df['downtime'].apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S")[:-4]+'0:00')
        self.up_down_df['downtime_h'] = self.up_down_df['downtime'].apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S")[:-5]+'00:00')



        # 没掉线的ONU
        tab_s, tab_min, tab_10min, tab_h = st.tabs(['s', 'min', '10min', 'h'])
        with tab_s:
            time_groupby_df_s = self.get_time_groupby_df("downtime")

        with tab_min:
            time_groupby_df_min = self.get_time_groupby_df("downtime_min")

        with tab_10min:
            time_groupby_df_10min = self.get_time_groupby_df("downtime_10min")

        with tab_h:
            time_groupby_df_h = self.get_time_groupby_df("downtime_h")



        # todo: 画折线图，表示掉线时间点和个数情况（分为掉线和掉电）

        # todo: 某一段时间范围内，ONU掉线次数，找出掉线次数少，没有被影响过的ONU

        # todo: not_included要排除掉最后一次up离现在很久的ONU, 当时不在线的ONU

        # todo: 最近一次在线时长

        # todo: 对上线时间进行排序

        # todo: 显示该时间点在线的ONU、不在线的ONU（不含近一个月都不在线的ONU）（在线的ONU在时间之内）

        # todo: 看指定时间段内，表，看谁先下线

        # todo: 增加onu维度，看重要时间区间，没有掉线的次数

        # todo: 整体时间线，downtime和uptime整合在一起

        # todo: 如果可以点击一条1h的，显示具体的条目就好了。。

    def analyze_onu(self):
        # 疑似垃圾数据
        pass

    def get_online_interval(self):
        pass

    def explain_onu(self, row):
        # expect the element as a list
        if row:
            # get the last one
            last_down_time = row[-1]
            # 大于一个月
            if (pd.to_datetime(last_down_time) < pd.to_datetime(DOWNTIME_ENDTIME) - pd.Timedelta(days=31)):
                return '大于一月没上线'
            else:
                return ''

    def get_onu_state(self, time_str):
        # input: time
        # output: online_onu
        # 每个ONU，遍历区间，看看时间点在不在每个区间内
        onu_groupby_df = up_down_df.groupby(['onuid', 'onusn'])[['up_time', 'down_time']].agg(list)
        onu_groupby_df['online_interval'] = onu_groupby_df.apply(self.get_online_interval, axis=1)
        onu_groupby_df['onu_explain'] = onu_groupby_df['uptime'].apply(self.explain_onu)


class MA5800Processor():
    def __init__(self, up_down_df):
        self.null_time_str = '-'
        self.up_down_df = self.process_up_down_df(up_down_df)
        self.all_onusn_set = set(up_down_df["onusn"])
        self.all_onuid_set = set(up_down_df["onuid"])

    def standard_downtime(self, col):
        if col == self.null_time_str:
            return DOWNTIME_ENDTIME+'+08:00'
        else:
            return col

    def get_onu_label(self, row):
        return f"{row['onuid']} {row['onusn']}"

    def process_up_down_df(self, up_down_df):
        # uptime
        up_down_df = up_down_df.drop(up_down_df[up_down_df['uptime'] == self.null_time_str].index)
        up_down_df['uptime'] = pd.to_datetime(up_down_df['uptime'])
        # downtime
        up_down_df['downtime'] = pd.to_datetime(up_down_df['downtime'].apply(self.standard_downtime))
        # cause
        up_down_df['cause'] = up_down_df['cause'].fillna("-")

        # label
        up_down_df['onu'] = up_down_df.apply(self.get_onu_label, axis=1)
        up_down_df = up_down_df.sort_values('onu')

        return up_down_df
    def plot_up_down_df_timeline(self):
        up_down_df_show = self.up_down_df
        # up_down_df_show = up_down_df[up_down_df['cause']!='DyingGasp']

        fig = px.timeline(up_down_df_show, x_start="uptime", x_end="downtime", y="onu", color='onuid',
                          hover_data=['cause', 'time_ind'])  # , facet_row='current_speed_mode')

        fig.update_layout(yaxis=dict(
            fixedrange=True
        ))

        fig.update_layout(width=1500, height=1200)

        fig.update_xaxes(rangeslider_visible=True)

        st.plotly_chart(fig)

    def get_los_dying_count(self, row):
        dying_num = 0
        losi_num = 0
        dying_onuid_list = []
        losi_onuid_list = []
        dying_onusn_list = []
        losi_onusn_list = []

        # print(row['cause'])
        for i in range(len(row["cause"])):
            try:
                if "dying-gasp" in row["cause"][i]:

                    dying_num += 1
                    dying_onuid_list.append(row["onuid"][i])
                    dying_onusn_list.append(row["onusn"][i])

                elif "LO" in row["cause"][i]:
                    losi_num += 1
                    losi_onuid_list.append(row["onuid"][i])
                    losi_onusn_list.append(row["onusn"][i])
            except:
                pass
                # print(row["cause"])

        return losi_num, dying_num, losi_onuid_list, losi_onusn_list, dying_onuid_list, dying_onusn_list

    def get_not_included_onu(self, row):

        not_inc_onusn_set = self.all_onusn_set - set(row["onusn"])
        not_inc_onuid_set = self.all_onuid_set - set(row["onuid"])
        not_inc_onu_num = len(not_inc_onusn_set)
        return not_inc_onu_num, list(not_inc_onusn_set), list(not_inc_onuid_set)


    def get_time_groupby_df(self, groupby_col):
        time_groupby_df = self.up_down_df.sort_values("downtime").groupby(groupby_col)[["onuid", "onusn", "cause"]].agg(list)
        # print("down时间点")
        time_groupby_df["总掉线次数"] = time_groupby_df["onusn"].apply(lambda x: len(x))
        time_groupby_df["总掉线ONU个数"] = time_groupby_df["onusn"].apply(lambda x: len(set(x)))

        time_groupby_df["losi次数"], time_groupby_df["dying-gasp次数"], time_groupby_df[
            "losi_onuid_list"], \
            time_groupby_df["losi_onusn_list"], time_groupby_df["dying_onuid_list"], time_groupby_df[
            "dying_onusn_list"] = zip(*time_groupby_df.apply(self.get_los_dying_count, axis=1))

        # 这段时间内没有上线记录的ONU，标出
        time_groupby_df['not_inc_onu_num'], time_groupby_df['not_inc_onusn_set'], time_groupby_df[
            'not_inc_onuid_set'] = zip(
            *time_groupby_df.apply(self.get_not_included_onu, axis=1))
        time_groupby_df = time_groupby_df.sort_values("losi次数", ascending=False)


        fig = px.line(time_groupby_df.reset_index().sort_values(groupby_col),
                      x=groupby_col, y="losi次数",
                      hover_data=["losi_onuid_list", "not_inc_onuid_set"])
        fig.update_xaxes(rangeslider_visible=True,
                         rangeselector=dict(
                             buttons=list([
                                 dict(count=1, label="1m", step="month", stepmode="backward"),
                                 dict(count=6, label="6m", step="month", stepmode="backward"),
                                 dict(count=1, label="YTD", step="year", stepmode="todate"),
                                 dict(count=1, label="1y", step="year", stepmode="backward"),
                                 dict(step="all")
                             ])
                         )

                         )

        st.dataframe(time_groupby_df)
        st.plotly_chart(fig)

        return time_groupby_df

    def analyze_time(self):
        onu_num = len(self.all_onusn_set)

        st.success(f"pon下共{onu_num}个onu")

        # s, min, h聚合
        # 华为的要改，华为的有+08:00
        self.up_down_df['downtime_min'] = self.up_down_df['downtime'].apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S")[:-3]+':00')
        self.up_down_df['downtime_10min'] = self.up_down_df['downtime'].apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S")[:-4]+'0:00')
        self.up_down_df['downtime_h'] = self.up_down_df['downtime'].apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S")[:-5]+'00:00')



        # 没掉线的ONU
        tab_s, tab_min, tab_10min, tab_h = st.tabs(['s', 'min', '10min', 'h'])
        with tab_s:
            time_groupby_df_s = self.get_time_groupby_df("downtime")

        with tab_min:
            time_groupby_df_min = self.get_time_groupby_df("downtime_min")

        with tab_10min:
            time_groupby_df_10min = self.get_time_groupby_df("downtime_10min")

        with tab_h:
            time_groupby_df_h = self.get_time_groupby_df("downtime_h")

    def analyze_onu(self):

        # 疑似垃圾数据
        pass




uploaded_table_file = st.file_uploader("上传表格", type=["xlsx", "csv"])

if uploaded_table_file is not None:
    if uploaded_table_file.type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        up_down_df = pd.read_excel(uploaded_table_file, sheet_name=0)

    # if csv, todo
    elif uploaded_table_file.type == "text/csv":
        up_down_df = pd.read_csv(uploaded_table_file)

    DOWNTIME_ENDTIME = convert_time_format(uploaded_table_file.name)
    DEVICE_TYPE = ''
    if 'C600' in uploaded_table_file.name:
        DEVICE_TYPE = 'C600'
        df_processor = C600Processor(up_down_df)
    elif 'MA5800' in uploaded_table_file.name:
        DEVICE_TYPE = 'MA5800'
        df_processor = MA5800Processor(up_down_df)

    print(DEVICE_TYPE)
    st.success(f"读取文件{uploaded_table_file.name}")
    st.success(f"上下线记录抓取时间：{DOWNTIME_ENDTIME}")

    # 显示大图
    with st.container(border=True):
        df_processor.plot_up_down_df_timeline()
        df_processor.analyze_time()





