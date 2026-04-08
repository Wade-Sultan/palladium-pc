defmodule AdminWeb.Live.PartQueries do
  import Ecto.Query

  def cpu(query, _live_action, _assigns), do: from(p in query, where: p.part_type == "cpu")
  def gpu(query, _live_action, _assigns), do: from(p in query, where: p.part_type == "gpu")
  def ram(query, _live_action, _assigns), do: from(p in query, where: p.part_type == "ram")
  def psu(query, _live_action, _assigns), do: from(p in query, where: p.part_type == "psu")
  def fan(query, _live_action, _assigns), do: from(p in query, where: p.part_type == "fan")
  def storage(query, _live_action, _assigns), do: from(p in query, where: p.part_type == "storage")
  def case_part(query, _live_action, _assigns), do: from(p in query, where: p.part_type == "case")
  def motherboard(query, _live_action, _assigns), do: from(p in query, where: p.part_type == "motherboard")
  def cpu_cooler(query, _live_action, _assigns), do: from(p in query, where: p.part_type == "cpucooler")
end
