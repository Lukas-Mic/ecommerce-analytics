{#- Używa dokładnie nazw schematów z dbt_project.yml (staging, intermediate, marts)
    zamiast domyślnego prefiksu "analytics_staging" itd. -#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
