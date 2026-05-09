defmodule AdminWeb.Live.PartQueries do
  import Ecto.Query

  def cpu(query, _live_action, _assigns) do
    from c in query,
      join: p in Admin.Schema.PCPart, on: c.id == p.id,
      select_merge: %{
        name: p.name,
        manufacturer: p.manufacturer,
        model_number: p.model_number,
        year_released: p.year_released,
        is_active: p.is_active,
        ddr_generation_input: fragment("coalesce(array_to_string(?, ', '), '')", c.ddr_generation),
        supported_features_input: fragment("coalesce(array_to_string(?, ', '), '')", c.supported_features),
        benchmark_scores_input: fragment("coalesce(?::text, '')", c.benchmark_scores)
      }
  end

  def gpu(query, _live_action, _assigns) do
    from c in query,
      join: p in Admin.Schema.PCPart, on: c.id == p.id,
      select_merge: %{
        name: p.name,
        manufacturer: p.manufacturer,
        model_number: p.model_number,
        year_released: p.year_released,
        is_active: p.is_active,
        supported_features_input: fragment("coalesce(array_to_string(?, ', '), '')", c.supported_features),
        benchmark_scores_input: fragment("coalesce(?::text, '')", c.benchmark_scores)
      }
  end

  def motherboard(query, _live_action, _assigns) do
    from c in query,
      join: p in Admin.Schema.PCPart, on: c.id == p.id,
      select_merge: %{
        name: p.name,
        manufacturer: p.manufacturer,
        model_number: p.model_number,
        year_released: p.year_released,
        is_active: p.is_active
      }
  end

  def ram(query, _live_action, _assigns) do
    from c in query,
      join: p in Admin.Schema.PCPart, on: c.id == p.id,
      select_merge: %{
        name: p.name,
        manufacturer: p.manufacturer,
        model_number: p.model_number,
        year_released: p.year_released,
        is_active: p.is_active
      }
  end

  def storage(query, _live_action, _assigns) do
    from c in query,
      join: p in Admin.Schema.PCPart, on: c.id == p.id,
      select_merge: %{
        name: p.name,
        manufacturer: p.manufacturer,
        model_number: p.model_number,
        year_released: p.year_released,
        is_active: p.is_active
      }
  end

  def psu(query, _live_action, _assigns) do
    from c in query,
      join: p in Admin.Schema.PCPart, on: c.id == p.id,
      select_merge: %{
        name: p.name,
        manufacturer: p.manufacturer,
        model_number: p.model_number,
        year_released: p.year_released,
        is_active: p.is_active
      }
  end

  def case_part(query, _live_action, _assigns) do
    from c in query,
      join: p in Admin.Schema.PCPart, on: c.id == p.id,
      select_merge: %{
        name: p.name,
        manufacturer: p.manufacturer,
        model_number: p.model_number,
        year_released: p.year_released,
        is_active: p.is_active,
        supported_mobo_form_factors_input:
          fragment("coalesce(array_to_string(?, ', '), '')", c.supported_mobo_form_factors)
      }
  end

  def cpu_cooler(query, _live_action, _assigns) do
    from c in query,
      join: p in Admin.Schema.PCPart, on: c.id == p.id,
      select_merge: %{
        name: p.name,
        manufacturer: p.manufacturer,
        model_number: p.model_number,
        year_released: p.year_released,
        is_active: p.is_active,
        supported_sockets_input:
          fragment("coalesce(array_to_string(?, ', '), '')", c.supported_sockets)
      }
  end

  def fan(query, _live_action, _assigns) do
    from c in query,
      join: p in Admin.Schema.PCPart, on: c.id == p.id,
      select_merge: %{
        name: p.name,
        manufacturer: p.manufacturer,
        model_number: p.model_number,
        year_released: p.year_released,
        is_active: p.is_active
      }
  end
end
