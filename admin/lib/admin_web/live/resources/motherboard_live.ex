defmodule AdminWeb.Live.MotherboardLive do
  use Backpex.LiveResource,
    adapter: Backpex.Adapters.Ecto,
    adapter_config: [
      repo: Admin.Repo,
      schema: Admin.Schema.PCPart,
      update_changeset: &Admin.Schema.PCPart.changeset/3,
      create_changeset: &Admin.Schema.PCPart.changeset/3,
      item_query: &AdminWeb.Live.PartQueries.motherboard/3
    ]

  @impl Backpex.LiveResource
  def layout(_assigns), do: {AdminWeb.Layouts, :admin}

  @impl Backpex.LiveResource
  def singular_name, do: "Motherboard"

  @impl Backpex.LiveResource
  def plural_name, do: "Motherboards"

  @impl Backpex.LiveResource
  def fields do
    [
      name: %{module: Backpex.Fields.Text, label: "Name"},
      manufacturer: %{module: Backpex.Fields.Text, label: "Manufacturer"},
      model_number: %{module: Backpex.Fields.Text, label: "Model Number"},
      year_released: %{module: Backpex.Fields.Number, label: "Year"},
      is_active: %{module: Backpex.Fields.Boolean, label: "Active"}
    ]
  end
end
