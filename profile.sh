python -m cProfile -s time $1 > tmp_profile_output && head -n 50 tmp_profile_output
