"""DBP Demo — runs all 7 scenarios."""

from scenarios.scenario_1_basic import run as s1
from scenarios.scenario_2_heritage import run as s2
from scenarios.scenario_3_readin import run as s3
from scenarios.scenario_4_chain import run as s4
from scenarios.scenario_5_policies import run as s5
from scenarios.scenario_6_multiagent import run as s6
from scenarios.scenario_7_derived_data import run as s7


def main():
    header = "=" * 52
    print(f"\n{header}")
    print("  D B P   D E M O   —   D a t a   B o u n d a r y   P r o t o c o l")
    print(f"{header}\n")

    s1()
    s2()
    s3()
    s4()
    s5()
    s6()
    s7()

    print(f"{header}")
    print("  All scenarios complete.")
    print(f"{header}\n")


if __name__ == "__main__":
    main()
