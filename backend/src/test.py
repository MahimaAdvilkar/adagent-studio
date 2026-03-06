import os

from payments_py import Payments, PaymentOptions


api_key = (os.getenv("NVM_API_KEY") or "").strip()
if not api_key:
    raise SystemExit("Set NVM_API_KEY in your environment before running this script.")

p = Payments(PaymentOptions(nvm_api_key=api_key, environment="sandbox"))
plan_info = p.plans.get_plan(plan_id="43955667645714568092057142565359274237259428265532767327265493246604990476175")
print(plan_info)  # should contain endpoint info