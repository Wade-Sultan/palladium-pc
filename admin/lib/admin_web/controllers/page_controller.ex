defmodule AdminWeb.PageController do
  use AdminWeb, :controller

  def home(conn, _params) do
    render(conn, :home)
  end
end
