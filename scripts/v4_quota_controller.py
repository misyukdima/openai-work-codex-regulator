#!/usr/bin/env python3
"""v4 active-work-window weekly Work/Codex quota controller."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import argparse
import json
import math

BASE_WEEKLY_RESERVE_PP=10.0
RESERVE_FRACTION_CAP=0.50
RESERVE_RELEASE_ACTIVE_MINUTES=360.0
DEFAULT_START_MINUTE=9*60
DEFAULT_SOFT_END_MINUTE=22*60
DEFAULT_HARD_END_MINUTE=23*60
DEFAULT_ACTIVE_WEEKDAYS=(0,1,2,3,4,5,6)

def clamp(v:float,lo:float,hi:float)->float:
    return max(lo,min(hi,v))

@dataclass(frozen=True)
class WorkSchedule:
    start_minute:int=DEFAULT_START_MINUTE
    soft_end_minute:int=DEFAULT_SOFT_END_MINUTE
    hard_end_minute:int=DEFAULT_HARD_END_MINUTE
    active_weekdays:tuple[int,...]=DEFAULT_ACTIVE_WEEKDAYS
    def __post_init__(self)->None:
        if not (0<=self.start_minute<self.soft_end_minute<=self.hard_end_minute<=1440):
            raise ValueError("invalid work window")
        if not self.active_weekdays or any(d<0 or d>6 for d in self.active_weekdays):
            raise ValueError("invalid active weekdays")
    @property
    def daily_active_minutes(self)->int:
        return self.hard_end_minute-self.start_minute

def _day_point(day:datetime,minute:int)->datetime:
    return day.replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(minutes=minute)

def active_minutes_between(start:datetime,end:datetime,schedule:WorkSchedule)->float:
    if end<=start:
        return 0.0
    total=0.0
    day=start.replace(hour=0,minute=0,second=0,microsecond=0)
    last=end.replace(hour=0,minute=0,second=0,microsecond=0)
    active=set(schedule.active_weekdays)
    while day<=last:
        if day.weekday() in active:
            lo=max(start,_day_point(day,schedule.start_minute))
            hi=min(end,_day_point(day,schedule.hard_end_minute))
            if hi>lo:
                total+=(hi-lo).total_seconds()/60.0
        day+=timedelta(days=1)
    return total

def reserve_pp(weekly_remaining_pp:float,anchor_active_minutes:float)->float:
    remaining=clamp(float(weekly_remaining_pp),0.0,100.0)
    if anchor_active_minutes<=0:
        return 0.0
    return min(BASE_WEEKLY_RESERVE_PP,RESERVE_FRACTION_CAP*remaining)

def target_cumulative_spend_pp(anchor_weekly_used_pp:float,anchor_active_minutes_to_reset:float,active_minutes_to_reset_now:float)->float:
    used=clamp(float(anchor_weekly_used_pp),0.0,100.0)
    a0=max(0.0,float(anchor_active_minutes_to_reset))
    a=clamp(float(active_minutes_to_reset_now),0.0,a0)
    remaining0=100.0-used
    if a0<=0:
        return remaining0
    reserve0=reserve_pp(remaining0,a0)
    schedulable0=max(0.0,remaining0-reserve0)
    scheduled_remaining=schedulable0*(a/a0)
    release_den=min(RESERVE_RELEASE_ACTIVE_MINUTES,a0)
    reserve_remaining=0.0 if release_den<=0 else reserve0*clamp(a/release_den,0.0,1.0)
    return clamp(remaining0-scheduled_remaining-reserve_remaining,0.0,remaining0)

@dataclass(frozen=True)
class RunwayStatus:
    anchor_weekly_used_pp:float
    current_weekly_used_pp:float
    anchor_active_minutes_to_reset:float
    active_minutes_to_reset_now:float
    actual_spend_since_anchor_pp:float
    base_lookahead_active_minutes:float
    max_advance_active_minutes:float
    base_action_headroom_pp:float
    max_advance_headroom_pp:float
    borrowable_extra_pp:float

def runway_status(anchor_weekly_used_pp:float,anchor_active_minutes_to_reset:float,current_weekly_used_pp:float,active_minutes_to_reset_now:float,schedule:WorkSchedule|None=None,meter_granularity_pp:float=1.0,scheduled_commitment_pp:float=0.0)->RunwayStatus:
    schedule=schedule or WorkSchedule()
    a0=max(0.0,float(anchor_active_minutes_to_reset))
    a=clamp(float(active_minutes_to_reset_now),0.0,a0)
    current=clamp(float(current_weekly_used_pp),0.0,100.0)
    actual=max(0.0,current-clamp(float(anchor_weekly_used_pp),0.0,100.0))
    g=max(0.0,float(meter_granularity_pp))
    commitments=max(0.0,float(scheduled_commitment_pp))
    base_lookahead=min(a,float(schedule.daily_active_minutes))
    max_advance=min(a,float(schedule.daily_active_minutes*2))
    base_future=max(0.0,a-base_lookahead)
    max_future=max(0.0,a-max_advance)
    target_base=target_cumulative_spend_pp(anchor_weekly_used_pp,a0,base_future)
    target_max=target_cumulative_spend_pp(anchor_weekly_used_pp,a0,max_future)
    base=max(0.0,target_base-actual-commitments-g)
    maximum=max(0.0,target_max-actual-commitments-g)
    return RunwayStatus(float(anchor_weekly_used_pp),current,a0,a,actual,base_lookahead,max_advance,base,maximum,max(0.0,maximum-base))

def secondary_limit_policy(window_present:bool|None)->str:
    if window_present is True:
        return "ENFORCE_INDEPENDENTLY"
    if window_present is False:
        return "NOT_APPLICABLE_FROM_CURRENT_SNAPSHOT"
    return "UNKNOWN_REFRESH_IF_DECISION_SENSITIVE"

def self_test()->None:
    s=WorkSchedule()
    assert s.daily_active_minutes==14*60
    assert active_minutes_between(datetime(2026,9,24,8),datetime(2026,9,24,23),s)==14*60
    assert active_minutes_between(datetime(2026,9,24,21),datetime(2026,9,25,11),s)==4*60
    a0=7*14*60
    st=runway_status(0.0,a0,0.0,a0,s,meter_granularity_pp=0.0)
    assert st.base_action_headroom_pp>0
    assert st.max_advance_headroom_pp>st.base_action_headroom_pp
    assert math.isclose(target_cumulative_spend_pp(0.0,a0,a0),0.0,abs_tol=1e-9)
    assert secondary_limit_policy(False)=="NOT_APPLICABLE_FROM_CURRENT_SNAPSHOT"
    assert secondary_limit_policy(True)=="ENFORCE_INDEPENDENTLY"

def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--anchor-used",type=float,required=True)
    p.add_argument("--anchor-active-minutes",type=float,required=True)
    p.add_argument("--current-used",type=float,required=True)
    p.add_argument("--active-minutes-now",type=float,required=True)
    p.add_argument("--start-minute",type=int,default=DEFAULT_START_MINUTE)
    p.add_argument("--soft-end-minute",type=int,default=DEFAULT_SOFT_END_MINUTE)
    p.add_argument("--hard-end-minute",type=int,default=DEFAULT_HARD_END_MINUTE)
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test:
        self_test()
    schedule=WorkSchedule(args.start_minute,args.soft_end_minute,args.hard_end_minute)
    result=runway_status(args.anchor_used,args.anchor_active_minutes,args.current_used,args.active_minutes_now,schedule)
    print(json.dumps(asdict(result),indent=2))

if __name__=="__main__":
    main()
