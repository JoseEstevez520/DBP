from dbp import Boundary, Clearance, Label, Policy

boundary = Boundary()

fitness_data = Label({"fitness"})

coach = Clearance({"identity", "fitness", "schedule"})
developer = Clearance({"identity", "project", "schedule"})

result_coach = boundary.check(fitness_data, coach, Policy.ANY)
result_dev = boundary.check(fitness_data, developer, Policy.ANY)

print(f"Coach sees [fitness]:       {result_coach.value}")
print(f"Developer sees [fitness]:   {result_dev.value}")
