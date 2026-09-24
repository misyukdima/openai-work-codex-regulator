#!/usr/bin/env python3
"""v4 active-work-window Work/Codex quota controller."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import argparse
import json
import math
import statistics
from typing import Iterable, Sequence

BASE_WEEKLY_RESERVE_PP=10.0
RESERVE_FRACTION_CAP=0.50
RESERVE_RELEASE_ACTIVE_MINUTES=360.0
DEFAULT_START_MINUTE=9*60
DEFAULT_SOFT_END_MINUTE=22*60
DEFAULT_HARD_END_MINUTE=23*60
DEFAULT_ACTIVE_WEEKDAYS=(0,1,2,3,4,5,6)
PACE_LEVELS={"NONE":0.0,"LOW":0.25,"MEDIUM":0.50,"HIGH":0.75,"CRITICAL":1.0}

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
    def normal_daily_minutes(self)->int:
        return self.soft_end_minute-self.start_minute
    @property
    def hard_daily_minutes(self)->int:
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
    base_lookahead=min(a,float(schedule.normal_daily_minutes))
    max_advance=min(a,float(schedule.hard_daily_minutes*2))
    target_base=target_cumulative_spend_pp(anchor_weekly_used_pp,a0,max(0.0,a-base_lookahead))
    target_max=target_cumulative_spend_pp(anchor_weekly_used_pp,a0,max(0.0,a-max_advance))
    base=max(0.0,target_base-actual-commitments-g)
    maximum=max(0.0,target_max-actual-commitments-g)
    return RunwayStatus(float(anchor_weekly_used_pp),current,a0,a,actual,base_lookahead,max_advance,base,maximum,max(0.0,maximum-base))

def _quantile_linear(values:Sequence[float],q:float)->float:
    ordered=sorted(float(v) for v in values)
    if not ordered:
        raise ValueError("quantile requires samples")
    if len(ordered)==1:
        return ordered[0]
    pos=(len(ordered)-1)*clamp(q,0.0,1.0)
    lo=math.floor(pos); hi=math.ceil(pos)
    if lo==hi:
        return ordered[lo]
    w=pos-lo
    return ordered[lo]*(1-w)+ordered[hi]*w

@dataclass(frozen=True)
class BurnEstimate:
    safe_burn_pp:float|None
    confidence:str
    method:str
    sample_count:int
    samples_pp:tuple[float,...]

def robust_safe_burn_pp(samples_pp:Iterable[float],meter_granularity_pp:float=1.0)->BurnEstimate:
    samples=tuple(max(0.0,float(x)) for x in samples_pp)[-5:]
    g=max(0.0,float(meter_granularity_pp))
    n=len(samples)
    if n==0:
        return BurnEstimate(None,"UNKNOWN","no-compatible-history",0,samples)
    if n==1:
        x=samples[0]
        return BurnEstimate(x+max(g,0.50*x),"LOW","single-sample-50pct-bootstrap",1,samples)
    if n==2:
        m=max(samples)
        return BurnEstimate(m+max(g,0.25*m),"LOW","two-sample-max-25pct-bootstrap",2,samples)
    med=statistics.median(samples)
    mad=statistics.median(abs(x-med) for x in samples)
    sigma=1.4826*mad
    p80=_quantile_linear(samples,0.80)
    safe=max(p80,med+1.645*sigma)+g
    return BurnEstimate(safe,"HIGH" if n>=5 else "MEDIUM","median-mad-p80-one-sided-margin",n,samples)

def pace_risk(level:str|float)->float:
    if isinstance(level,str):
        key=level.strip().upper()
        if key in PACE_LEVELS:
            return PACE_LEVELS[key]
        return clamp(float(level),0.0,1.0)
    return clamp(float(level),0.0,1.0)

@dataclass(frozen=True)
class Admission:
    decision:str
    quality_floor:str
    safe_burn_pp:float|None
    base_headroom_pp:float
    max_headroom_pp:float
    quota_risk_if_launch:float
    pace_risk_if_defer:float

def admission(status:RunwayStatus,burn:BurnEstimate,pace_risk_if_defer:str|float="MEDIUM",quality_sufficient:bool=True)->Admission:
    p=pace_risk(pace_risk_if_defer)
    if not quality_sufficient:
        return Admission("DEFER_FOR_QUALITY","NON_NEGOTIABLE",burn.safe_burn_pp,status.base_action_headroom_pp,status.max_advance_headroom_pp,0.0,p)
    if burn.safe_burn_pp is None:
        return Admission("CALIBRATE_OR_PREPARE","NON_NEGOTIABLE",None,status.base_action_headroom_pp,status.max_advance_headroom_pp,0.0,p)
    safe=burn.safe_burn_pp
    if safe<=status.base_action_headroom_pp:
        return Admission("LAUNCH_BASE","NON_NEGOTIABLE",safe,status.base_action_headroom_pp,status.max_advance_headroom_pp,0.0,p)
    extra=max(0.0,status.borrowable_extra_pp)
    needed=max(0.0,safe-status.base_action_headroom_pp)
    if extra<=0 or safe>status.max_advance_headroom_pp:
        return Admission("PROGRESS_ALTERNATIVE_OR_DEFER","NON_NEGOTIABLE",safe,status.base_action_headroom_pp,status.max_advance_headroom_pp,1.0,p)
    q=clamp(needed/extra,0.0,1.0)
    decision="LAUNCH_WITH_ADVANCE" if q<=p else "PROGRESS_ALTERNATIVE_OR_DEFER"
    return Admission(decision,"NON_NEGOTIABLE",safe,status.base_action_headroom_pp,status.max_advance_headroom_pp,q,p)

def secondary_limit_policy(window_present:bool|None)->str:
    if window_present is True:
        return "ENFORCE_INDEPENDENTLY"
    if window_present is False:
        return "NOT_APPLICABLE_FROM_CURRENT_SNAPSHOT"
    return "UNKNOWN_REFRESH_IF_DECISION_SENSITIVE"

def self_test()->None:
    s=WorkSchedule()
    assert s.normal_daily_minutes==13*60
    assert s.hard_daily_minutes==14*60
    assert active_minutes_between(datetime(2026,9,24,8),datetime(2026,9,24,23),s)==14*60
    assert active_minutes_between(datetime(2026,9,24,21),datetime(2026,9,25,11),s)==4*60
    a0=7*14*60
    st=runway_status(0.0,a0,0.0,a0,s,meter_granularity_pp=0.0)
    assert st.base_lookahead_active_minutes==13*60
    assert st.max_advance_active_minutes==2*14*60
    assert st.max_advance_headroom_pp>st.base_action_headroom_pp>0
    assert math.isclose(target_cumulative_spend_pp(0.0,a0,a0),0.0,abs_tol=1e-9)
    b=robust_safe_burn_pp([3,4,4,5,6],1.0)
    assert b.safe_burn_pp is not None and b.safe_burn_pp>=6 and b.confidence=="HIGH"
    assert admission(st,BurnEstimate(None,"UNKNOWN","test",0,())).decision=="CALIBRATE_OR_PREPARE"
    assert admission(st,b,"CRITICAL",False).decision=="DEFER_FOR_QUALITY"
    assert secondary_limit_policy(False)=="NOT_APPLICABLE_FROM_CURRENT_SNAPSHOT"
    assert secondary_limit_policy(True)=="ENFORCE_INDEPENDENTLY"

def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--anchor-used",type=float,required=True)
    p.add_argument("--anchor-active-minutes",type=float,required=True)
    p.add_argument("--current-used",type=float,required=True)
    p.add_argument("--active-minutes-now",type=float,required=True)
    p.add_argument("--samples",default="")
    p.add_argument("--pace-risk",default="MEDIUM")
    p.add_argument("--start-minute",type=int,default=DEFAULT_START_MINUTE)
    p.add_argument("--soft-end-minute",type=int,default=DEFAULT_SOFT_END_MINUTE)
    p.add_argument("--hard-end-minute",type=int,default=DEFAULT_HARD_END_MINUTE)
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test:
        self_test()
    schedule=WorkSchedule(args.start_minute,args.soft_end_minute,args.hard_end_minute)
    status=runway_status(args.anchor_used,args.anchor_active_minutes,args.current_used,args.active_minutes_now,schedule)
    payload={"runway":asdict(status)}
    samples=[float(x.strip()) for x in args.samples.split(",") if x.strip()]
    if samples:
        burn=robust_safe_burn_pp(samples)
        payload["burn_estimate"]=asdict(burn)
        payload["admission"]=asdict(admission(status,burn,args.pace_risk,True))
    print(json.dumps(payload,indent=2))

if __name__=="__main__":
    main()
