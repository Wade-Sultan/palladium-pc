defmodule AdminWeb.Router do
  use AdminWeb, :router

  import Backpex.Router

  pipeline :browser do
    plug :accepts, ["html"]
    plug :fetch_session
    plug :fetch_live_flash
    plug :put_root_layout, html: {AdminWeb.Layouts, :root}
    plug :protect_from_forgery
    plug :put_secure_browser_headers
  end

  pipeline :api do
    plug :accepts, ["json"]
  end

  scope "/", AdminWeb do
    pipe_through :browser

    live "/", HomeLive, :index
  end

  scope "/admin", AdminWeb do
    pipe_through :browser

    backpex_routes()

    live_session :admin,
      layout: {AdminWeb.Layouts, :admin} do
      live_resources "/reference-builds", Live.ReferenceBuildLive
      live_resources "/cpus", Live.CPULive
      live_resources "/cpu-coolers", Live.CPUCoolerLive
      live_resources "/motherboards", Live.MotherboardLive
      live_resources "/ram", Live.RAMLive
      live_resources "/storage", Live.StorageLive
      live_resources "/gpus", Live.GPULive
      live_resources "/cases", Live.CaseLive
      live_resources "/psus", Live.PSULive
      live_resources "/fans", Live.FanLive
      live_resources "/users", Live.UserLive

      live "/llm-analytics", Live.LLMAnalyticsLive, :index
    end
  end

  # Enable LiveDashboard and Swoosh mailbox preview in development
  if Application.compile_env(:admin, :dev_routes) do
    import Phoenix.LiveDashboard.Router

    scope "/dev" do
      pipe_through :browser

      live_dashboard "/dashboard", metrics: AdminWeb.Telemetry
      forward "/mailbox", Plug.Swoosh.MailboxPreview
    end
  end
end
