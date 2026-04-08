defmodule AdminWeb.Live.ReferenceBuildLive do
  use Backpex.LiveResource,
    adapter: Backpex.Adapters.Ecto,
    adapter_config: [
      repo: Admin.Repo,
      schema: Admin.Schema.ReferenceBuild,
      update_changeset: &Admin.Schema.ReferenceBuild.changeset/3,
      create_changeset: &Admin.Schema.ReferenceBuild.changeset/3
    ]

  @impl Backpex.LiveResource
  def layout(_assigns), do: {AdminWeb.Layouts, :admin}

  @impl Backpex.LiveResource
  def singular_name, do: "Reference Build"

  @impl Backpex.LiveResource
  def plural_name, do: "Reference Builds"

  @impl Backpex.LiveResource
  def fields do
    [
      build_key: %{module: Backpex.Fields.Text, label: "Build Key"},
      label: %{module: Backpex.Fields.Text, label: "Label"},
      description: %{module: Backpex.Fields.Textarea, label: "Description"},
      total_approx: %{module: Backpex.Fields.Number, label: "Approx. Price (cents)"},
      is_active: %{module: Backpex.Fields.Boolean, label: "Active"}
    ]
  end
end
