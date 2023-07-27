#  Copyright (c) ZenML GmbH 2022. All Rights Reserved.

#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at:

#       https://www.apache.org/licenses/LICENSE-2.0

#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
#  or implied. See the License for the specific language governing
#  permissions and limitations under the License.
"""Functionality to handle downloading ZenML stacks via the CLI."""

import os
from typing import Any, Dict, List, Optional, Union, cast

import click
from rich.text import Text

from zenml.cli import utils as cli_utils
from zenml.cli.stack import stack
from zenml.constants import (
    ALPHA_MESSAGE,
    STACK_RECIPE_MODULAR_RECIPES,
)
from zenml.io.fileio import remove
from zenml.logger import get_logger
from zenml.mlstacks.utils import (
    convert_click_params_to_mlstacks_primitives,
    convert_mlstacks_primitives_to_dicts,
    import_new_stack,
    stack_exists,
    stack_spec_exists,
    verify_mlstacks_installation,
    verify_spec_and_tf_files_exist,
)
from zenml.recipes import GitStackRecipesHandler
from zenml.utils import yaml_utils
from zenml.utils.analytics_utils import AnalyticsEvent, event_handler
from zenml.utils.io_utils import create_dir_recursive_if_not_exists
from zenml.utils.yaml_utils import write_yaml

logger = get_logger(__name__)


pass_git_stack_recipes_handler = click.make_pass_decorator(
    GitStackRecipesHandler, ensure=True
)


@stack.group(
    "recipe",
    help="Commands for using the stack recipes.",
    invoke_without_command=True,
)
def stack_recipe() -> None:
    """Access all ZenML stack recipes."""


@stack_recipe.command(name="list", help="List the available stack recipes.")
def list_stack_recipes() -> None:
    """List all available stack recipes.

    Args:
        git_stack_recipes_handler: The GitStackRecipesHandler instance.
    """
    cli_utils.warning(ALPHA_MESSAGE)
    stack_recipes = [
        {"stack_recipe_name": stack_recipe_instance}
        for stack_recipe_instance in get_recipe_names()
    ]
    cli_utils.print_table(stack_recipes)

    cli_utils.declare("\n" + "To get the latest list of stack recipes, run: ")
    text = Text("zenml stack recipe pull -y", style="markdown.code_block")
    cli_utils.declare(text)

    cli_utils.declare("\n" + "To pull any individual stack recipe, type: ")
    text = Text(
        "zenml stack recipe pull RECIPE_NAME", style="markdown.code_block"
    )
    cli_utils.declare(text)


@stack_recipe.command(help="Deletes the ZenML stack recipes directory.")
@click.option(
    "--path",
    "-p",
    type=click.STRING,
    default="zenml_stack_recipes",
    help="Relative path at which you want to clean the stack_recipe(s)",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Whether to skip the confirmation prompt.",
)
@pass_git_stack_recipes_handler
def clean(
    git_stack_recipes_handler: GitStackRecipesHandler,
    path: str,
    yes: bool,
) -> None:
    """Deletes the stack recipes directory from your working directory.

    Args:
        git_stack_recipes_handler: The GitStackRecipesHandler instance.
        path: The path at which you want to clean the stack_recipe(s).
        yes: Whether to skip the confirmation prompt.
    """
    stack_recipes_directory = os.path.join(os.getcwd(), path)
    if fileio.isdir(stack_recipes_directory) and (
        yes
        or cli_utils.confirmation(
            "Do you wish to delete the stack recipes directory? \n"
            f"{stack_recipes_directory}"
        )
    ):
        git_stack_recipes_handler.clean_current_stack_recipes()
        cli_utils.declare(
            "Stack recipes directory was deleted from your current working "
            "directory."
        )
    elif not fileio.isdir(stack_recipes_directory):
        cli_utils.error(
            f"Unable to delete the stack recipes directory - "
            f"{stack_recipes_directory} - "
            "as it was not found in your current working directory."
        )


@stack_recipe.command(help="Find out more about a stack recipe.")
@click.argument("stack_recipe_name")
def info(
    stack_recipe_name: str,
) -> None:
    """Find out more about a stack recipe.

    Outputs a pager view of the stack_recipe's README.md file.

    Args:
        stack_recipe_name: The name of the stack recipe.
    """
    recipe_readme = cli_utils.get_recipe_readme(stack_recipe_name)
    if recipe_readme is None:
        cli_utils.error(
            f"Unable to find stack recipe {stack_recipe_name}. "
            "Please check the name and try again."
        )
    cli_utils.print_markdown_with_pager(recipe_readme)


@stack_recipe.command(
    help="Describe the stack components and their tools that are "
    "created as part of this recipe."
)
@click.argument("stack_recipe_name")
def describe(
    stack_recipe_name: str,
) -> None:
    """Describe the stack components and their tools that are created as part of this recipe.

    Outputs the "Description" section of the recipe metadata.

    Args:
        stack_recipe_name: The name of the stack recipe.
    """
    stack_recipe_path = cli_utils.get_recipe_path(stack_recipe_name)
    if stack_recipe_path is None:
        cli_utils.error(
            f"Unable to find stack recipe {stack_recipe_name}. "
            "Please check the name and try again."
        )
    recipe_metadata_yaml = os.path.join(stack_recipe_path, "metadata.yaml")
    recipe_metadata = yaml_utils.read_yaml(recipe_metadata_yaml)
    logger.info(recipe_metadata["Description"])


@stack_recipe.command(help="The active version of the mlstacks recipes.")
def version() -> None:
    """The active version of the mlstacks recipes."""
    active_version = cli_utils.get_mlstacks_version()
    if active_version:
        cli_utils.declare(f"Running `mlstacks` version {active_version}.")
    else:
        cli_utils.warning("Unable to detect version.")


# @stack_recipe.command(
#     help="Run the stack_recipe that you previously pulled with "
#     "`zenml stack recipe pull`"
# )
# @click.argument("stack_recipe_name", required=True)
# @click.option(
#     "--path",
#     "-p",
#     type=click.STRING,
#     default="zenml_stack_recipes",
#     help="Relative path at which local stack recipe(s) should exist",
# )
# @click.option(
#     "--force",
#     "-f",
#     "force",
#     is_flag=True,
#     help="Force pull the stack recipe. This overwrites any existing recipe "
#     "files present locally, including the terraform state files and the "
#     "local configuration.",
# )
# @click.option(
#     "--stack-name",
#     "-n",
#     type=click.STRING,
#     required=False,
#     help="Set a name for the ZenML stack that will be imported from the YAML "
#     "configuration file which gets generated after deploying the stack recipe. "
#     "Defaults to the name of the stack recipe being deployed.",
# )
# @click.option(
#     "--import",
#     "import_stack_flag",
#     is_flag=True,
#     help="Import the stack automatically after the recipe is deployed.",
# )
# @click.option(
#     "--log-level",
#     type=click.Choice(
#         ["TRACE", "DEBUG", "INFO", "WARN", "ERROR"], case_sensitive=False
#     ),
#     help="Choose one of TRACE, DEBUG, INFO, WARN or ERROR (case insensitive) as "
#     "log level for the deploy operation.",
#     default="ERROR",
# )
# @click.option(
#     "--no-server",
#     is_flag=True,
#     help="Don't deploy ZenML even if there's no active cloud deployment.",
# )
# @click.option(
#     "--skip-pull",
#     is_flag=True,
#     help="Skip the pulling of the stack recipe before deploying. This should be used "
#     "if you have a local copy of your recipe already. Use the `--path` or `-p` flag to "
#     "specify the directory that hosts your recipe(s).",
# )
# @click.option(
#     "--artifact-store",
#     "-a",
#     help="The flavor of artifact store to use. "
#     "If not specified, the default artifact store will be used.",
# )
# @click.option(
#     "--orchestrator",
#     "-o",
#     help="The flavor of orchestrator to use. "
#     "If not specified, the default orchestrator will be used.",
# )
# @click.option(
#     "--container-registry",
#     "-c",
#     help="The flavor of container registry to use. "
#     "If not specified, no container registry will be deployed.",
# )
# @click.option(
#     "--model-deployer",
#     "-d",
#     help="The flavor of model deployer to use. "
#     "If not specified, no model deployer will be deployed.",
# )
# @click.option(
#     "--experiment-tracker",
#     "-e",
#     help="The flavor of experiment tracker to use. "
#     "If not specified, no experiment tracker will be deployed.",
# )
# @click.option(
#     "--secrets-manager",
#     "-x",
#     help="The flavor of secrets manager to use. "
#     "If not specified, no secrets manager will be deployed.",
# )
# @click.option(
#     "--step-operator",
#     "-s",
#     help="The flavor of step operator to use. "
#     "If not specified, no step operator will be deployed.",
# )
# @click.option(
#     "--config",
#     help="Use a YAML or JSON configuration or configuration file to pass"
#     "variables to the stack recipe.",
#     required=False,
#     type=str,
# )
# @pass_git_stack_recipes_handler
# @click.pass_context
# def deploy(
#     ctx: click.Context,
#     git_stack_recipes_handler: GitStackRecipesHandler,
#     stack_recipe_name: str,
#     artifact_store: Optional[str],
#     orchestrator: Optional[str],
#     container_registry: Optional[str],
#     model_deployer: Optional[str],
#     experiment_tracker: Optional[str],
#     secrets_manager: Optional[str],
#     step_operator: Optional[str],
#     path: str,
#     force: bool,
#     import_stack_flag: bool,
#     log_level: str,
#     no_server: bool,
#     skip_pull: bool,
#     stack_name: Optional[str],
#     config: Optional[str],
# ) -> None:
#     """Run the stack_recipe at the specified relative path.

#     `zenml stack_recipe pull <STACK_RECIPE_NAME>` has to be called with the
#     same relative path before the `deploy` command.

#     Args:
#         ctx: The click context.
#         git_stack_recipes_handler: The GitStackRecipesHandler instance.
#         stack_recipe_name: The name of the stack_recipe.
#         path: The path at which you want to install the stack_recipe(s).
#         force: Force pull the stack recipe, overwriting any existing files.
#         stack_name: A name for the ZenML stack that gets imported as a result
#             of the recipe deployment.
#         import_stack_flag: Import the stack automatically after the recipe is
#             deployed. The stack configuration file is always generated and
#             can be imported manually otherwise.
#         log_level: Choose one of TRACE, DEBUG, INFO, WARN or ERROR
#             (case-insensitive) as log level for the `deploy` operation.
#         no_server: Don't deploy ZenML even if there's no active cloud
#             deployment.
#         skip_pull: Skip the pull of the stack recipe before deploying. This
#             should be used if you have a local copy of your recipe already.
#         artifact_store: The flavor of artifact store to deploy. In the case of
#             the artifact store, it doesn't matter what you specify here, as
#             there's only one flavor per cloud provider and that will be deployed.
#         orchestrator: The flavor of orchestrator to use.
#         container_registry: The flavor of container registry to deploy. In the case of
#             the container registry, it doesn't matter what you specify here, as
#             there's only one flavor per cloud provider and that will be deployed.
#         model_deployer: The flavor of model deployer to deploy.
#         experiment_tracker: The flavor of experiment tracker to deploy.
#         secrets_manager: The flavor of secrets manager to deploy. In the case of
#             the secrets manager, it doesn't matter what you specify here, as
#             there's only one flavor per cloud provider and that will be deployed.
#         step_operator: The flavor of step operator to deploy.
#         config: Use a YAML or JSON configuration or configuration file to pass
#             variables to the stack recipe.
#     """
#     cli_utils.verify_mlstacks_installation()
#     cli_utils.warning(ALPHA_MESSAGE)
#     logger.info(
#         "Servers are no longer deployed by default. Please use the "
#         "`zenml deploy` command to deploy a ZenML server."
#     )

#     with event_handler(
#         event=AnalyticsEvent.RUN_STACK_RECIPE,
#         metadata={"stack_recipe_name": stack_recipe_name},
#         v2=True,
#     ) as handler:
#         # build a dict of all stack component options that have non-null values
#         stack_component_options = {
#             "artifact_store": artifact_store,
#             "orchestrator": orchestrator,
#             "container_registry": container_registry,
#             "model_deployer": model_deployer,
#             "experiment_tracker": experiment_tracker,
#             "secrets_manager": secrets_manager,
#             "step_operator": step_operator,
#         }

#         # filter out null values
#         stack_component_options = {
#             k: v for k, v in stack_component_options.items() if v is not None
#         }

#         handler.metadata.update(stack_component_options)

#         import python_terraform
#         import yaml

#         # get input variables
#         variables_dict: Dict[str, Any] = {}

#         if config:
#             if os.path.isfile(config):
#                 variables_dict = yaml_utils.read_yaml(config)
#             else:
#                 variables_dict = yaml.safe_load(config)
#             if not isinstance(variables_dict, dict):
#                 cli_utils.error(
#                     "The configuration argument must be JSON/YAML content or "
#                     "point to a valid configuration file."
#                 )

#         enabled_services = [
#             f"{name}_{value}"
#             for name, value in stack_component_options.items()
#             if name
#             not in [
#                 "artifact_store",
#                 "container_registry",
#                 "secrets_manager",
#             ]
#         ]
#         enabled_services = enabled_services + [
#             f"{name}"
#             for name, _ in stack_component_options.items()
#             if name
#             in [
#                 "artifact_store",
#                 "container_registry",
#                 "secrets_manager",
#             ]
#         ]

#         try:
#             stack_recipe = git_stack_recipes_handler.get_stack_recipes(
#                 stack_recipe_name
#             )[0]
#         except KeyError as e:
#             cli_utils.error(str(e))
#         else:
#             from zenml.recipes import (
#                 StackRecipeService,
#                 StackRecipeServiceConfig,
#             )

#             # warn that prerequisites should be met
#             metadata = stack_recipe.metadata
#             if not cli_utils.confirmation(
#                 "\nPrerequisites for running this recipe are as follows.\n"
#                 f"{metadata['Prerequisites']}"
#                 "\n\n Are all of these conditions met?"
#             ):
#                 cli_utils.error(
#                     "Prerequisites are not installed. Please make sure "
#                     "they are met and run deploy again."
#                 )

#             local_recipe_dir = Path(os.getcwd()) / path / stack_recipe_name

#             # create the stack recipe service.
#             stack_recipe_service_config = StackRecipeServiceConfig(
#                 directory_path=str(local_recipe_dir),
#                 skip_pull=skip_pull,
#                 force=force,
#                 log_level=log_level,
#                 enabled_services=enabled_services,
#                 input_variables=variables_dict,
#             )

#             stack_recipe_service = StackRecipeService.get_service(
#                 str(local_recipe_dir)
#             )

#             if stack_recipe_service:
#                 cli_utils.declare(
#                     "An existing deployment of the recipe found. "
#                     f"with path {local_recipe_dir}. "
#                     "Proceeding to update or create resources. "
#                 )
#             else:
#                 stack_recipe_service = StackRecipeService(
#                     config=stack_recipe_service_config,
#                     stack_recipe_name=stack_recipe_name,
#                 )

#             try:
#                 # start the service (the init and apply operation)
#                 stack_recipe_service.start()

#             except RuntimeError as e:
#                 cli_utils.error(
#                     f"Running recipe {stack_recipe_name} failed: {str(e)} "
#                     "\nPlease look at the error message to figure out "
#                     "why the command failed. If the error is due some wrong "
#                     "configuration, please consider checking the locals.tf "
#                     "file to verify if the inputs are correct. Most commonly, "
#                     "the command can fail due to a timeout error. In that "
#                     "case, please run zenml stack recipe deploy "
#                     f"{stack_recipe_name} again."
#                 )
#             except python_terraform.TerraformCommandError:
#                 cli_utils.error(
#                     f"Running recipe {stack_recipe_name} failed."
#                     "\nPlease look at the error message to figure out why the "
#                     "command failed. If the error is due some wrong "
#                     "configuration, please consider checking the locals.tf "
#                     "file to verify if the inputs are correct. Most commonly, "
#                     "the command can fail due to a timeout error. In that "
#                     "case, please run zenml stack recipe deploy "
#                     f"{stack_recipe_name} again."
#                 )
#         # invoke server deploy
#         if no_server:
#             logger.warning("The `--no-server` flag has been deprecated. ")
#         # get the stack yaml path
#         stack_yaml_file = os.path.join(
#             stack_recipe_service.config.directory_path,
#             stack_recipe_service.stack_file_path[2:],
#         )

#         logger.info(
#             "\nA stack configuration YAML file has been generated "
#             f"as part of the deployment of the {stack_recipe_name} "
#             f"recipe. Find it at {stack_yaml_file}."
#         )

#         if import_stack_flag:
#             logger.info(
#                 "\nThe flag `--import` is set. Proceeding "
#                 "to import a new ZenML stack from the created "
#                 "resources."
#             )
#             import_stack_name = stack_name if stack_name else stack_recipe_name
#             cli_utils.declare(
#                 "Importing a new stack with the name " f"{import_stack_name}."
#             )

#             # import deployed resources as ZenML stack
#             ctx.invoke(
#                 import_stack,
#                 stack_name=import_stack_name,
#                 filename=stack_yaml_file,
#                 ignore_version_mismatch=True,
#             )

#             cli_utils.declare(
#                 "Please consider creating any secrets that your "
#                 "stack components like the metadata store might "
#                 "need. You can inspect the fields of a stack "
#                 "component by running a describe command on them."
#             )
#             cli_utils.declare(
#                 "\n Run 'terraform output' in the recipe's "
#                 f"directory at {stack_recipe_service.config.directory_path} "
#                 "to get a list of outputs. To now retrieve sensitive "
#                 f"outputs, for example, the metadata-db-password "
#                 "use the command 'terraform output metadata-db-password' "
#                 "to get the value in the command-line."
#             )


@stack.command(help="Deploy a stack using mlstacks.")
@click.option(
    "--provider",
    "-p",
    "provider",
    required=True,
    type=click.Choice(STACK_RECIPE_MODULAR_RECIPES),
)
@click.option(
    "--stack-name",
    "-n",
    "stack_name",
    type=click.STRING,
    required=True,
    help="Set a name for the ZenML stack that will be imported from the YAML "
    "configuration file which gets generated after deploying the stack recipe. "
    "Defaults to the name of the stack recipe being deployed.",
)
@click.option(
    "--region",
    "-r",
    "region",
    type=click.STRING,
    required=True,
    help="The region to deploy the stack to.",
)
@click.option(
    "--import",
    "-i",
    "import_stack_flag",
    is_flag=True,
    help="Import the stack automatically after the stack is deployed.",
)
@click.option(
    "--artifact-store",
    "-a",
    "artifact_store",
    required=False,
    is_flag=True,
    help="Whether to deploy an artifact store.",
)
@click.option(
    "--container-registry",
    "-c",
    "container_registry",
    required=False,
    is_flag=True,
    help="Whether to deploy a container registry.",
)
@click.option(
    "--mlops-platform",
    "-m",
    "mlops_platform",
    type=click.Choice(["zenml"]),
    required=False,
    help="The flavor of MLOps platform to use."
    "If not specified, the default MLOps platform will be used.",
)
@click.option(
    "--orchestrator",
    "-o",
    required=False,
    type=click.Choice(
        ["kubernetes", "kubeflow", "tekton", "sagemaker", "vertex"]
    ),
    help="The flavor of orchestrator to use. "
    "If not specified, the default orchestrator will be used.",
)
@click.option(
    "--model-deployer",
    "-d",
    "model_deployer",
    required=False,
    type=click.Choice(["kserve", "seldon"]),
    help="The flavor of model deployer to use. ",
)
@click.option(
    "--experiment-tracker",
    "-e",
    "experiment_tracker",
    required=False,
    type=click.Choice(["mlflow"]),
    help="The flavor of experiment tracker to use.",
)
@click.option(
    "--step-operator",
    "-s",
    "step_operator",
    required=False,
    type=click.Choice(["sagemaker"]),
    help="The flavor of step operator to use.",
)
@click.option(  # TODO: handle this case
    "--file",
    "-f",
    "file",
    required=False,
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Use a YAML specification file as the basis of the stack deployment.",
)
@click.option(
    "--debug-mode",
    "-b",  # TODO: decide whether this is the best flag to use
    "debug_mode",
    is_flag=True,
    default=False,
    help="Whether to run the stack deployment in debug mode.",
)
@click.option(
    "--extra-config",
    "-x",
    "extra_config",
    multiple=True,
    help="Extra configurations as key=value pairs. This option can be used multiple times.",
)
@click.option(
    "--tags",
    "-t",
    "tags",
    required=False,
    type=click.STRING,
    help="Pass one or more extra configuration values.",
    multiple=True,
)
@click.option(
    "--extra-config",
    "-x",
    "extra_config",
    multiple=True,
    help="Extra configurations as key=value pairs. This option can be used multiple times.",
)
@click.pass_context
def deploy(
    ctx: click.Context,
    provider: str,
    stack_name: str,
    region: str,
    mlops_platform: Optional[str] = None,
    orchestrator: Optional[str] = None,
    model_deployer: Optional[str] = None,
    experiment_tracker: Optional[str] = None,
    step_operator: Optional[str] = None,
    import_stack_flag: Optional[bool] = None,
    artifact_store: Optional[bool] = None,
    container_registry: Optional[bool] = None,
    file: Optional[str] = None,
    debug_mode: Optional[bool] = None,
    tags: Optional[List[str]] = None,
    extra_config: Optional[List[str]] = None,
) -> None:
    """Run the stack_recipe at the specified relative path.

    `zenml stack_recipe pull <STACK_RECIPE_NAME>` has to be called with the
    same relative path before the `deploy` command.

    Args:
        ctx: The click context.
        provider: The cloud provider to deploy the stack to.
        force: Force pull the stack recipe, overwriting any existing files.
        stack_name: A name for the ZenML stack that gets imported as a result
            of the recipe deployment.
        import_stack_flag: Import the stack automatically after the recipe is
            deployed. The stack configuration file is always generated and
            can be imported manually otherwise.
        artifact_store: The flavor of artifact store to deploy. In the case of
            the artifact store, it doesn't matter what you specify here, as
            there's only one flavor per cloud provider and that will be deployed.
        orchestrator: The flavor of orchestrator to use.
        container_registry: The flavor of container registry to deploy. In the case of
            the container registry, it doesn't matter what you specify here, as
            there's only one flavor per cloud provider and that will be deployed.
        model_deployer: The flavor of model deployer to deploy.
        experiment_tracker: The flavor of experiment tracker to deploy.
        step_operator: The flavor of step operator to deploy.
        extra_config: Extra configurations as key=value pairs.
    """
    # TODO make these checks after the stack spec is created
    # handle at stack level as well as component level
    # delete stack spec if we error out
    if stack_exists(stack_name):
        cli_utils.error(
            f"Stack with name '{stack_name}' already exists. Please choose a "
            "different name."
        )
    elif stack_spec_exists(stack_name):
        cli_utils.error(
            f"Stack spec with name '{stack_name}' already exists. "
            "Please choose a different name."
        )

    verify_mlstacks_installation()
    from mlstacks.utils import zenml_utils

    cli_utils.warning(ALPHA_MESSAGE)

    cli_params: Dict[str, Any] = ctx.params
    stack, components = convert_click_params_to_mlstacks_primitives(cli_params)

    if not zenml_utils.has_valid_flavor_combinations(stack, components):
        cli_utils.error(
            "The specified stack and component flavors are not compatible "
            "with the provider or with one another. Please try again."
        )

    stack_dict, component_dicts = convert_mlstacks_primitives_to_dicts(
        stack, components
    )
    # write the stack and component yaml files
    from mlstacks.constants import MLSTACKS_PACKAGE_NAME

    spec_dir = (
        f"{click.get_app_dir(MLSTACKS_PACKAGE_NAME)}/stack_specs/{stack.name}"
    )
    create_dir_recursive_if_not_exists(spec_dir)

    stack_file_path = f"{spec_dir}/stack-{stack.name}.yaml"
    write_yaml(file_path=stack_file_path, contents=stack_dict)
    for component in component_dicts:
        write_yaml(
            file_path=f"{spec_dir}/{component['name']}.yaml",
            contents=component,
        )

    from mlstacks.utils import terraform_utils

    terraform_utils.deploy_stack(stack_file_path, debug_mode=debug_mode)

    if import_stack_flag:
        import_new_stack(
            provider=stack.provider, stack_file_path=stack_file_path
        )

    # # Parse the given args
    # # name is guaranteed to be set by parse_name_and_extra_arguments
    # name, parsed_args = cli_utils.parse_name_and_extra_arguments(
    #     list(extra_config) + [name], expand_args=True
    # )

    # # copy the terraform files to the config directory
    # try:
    #     terraform_utils.populate_tf_definitions(provider)
    # except FileExistsError:
    #     if cli_utils.confirmation(
    #         "The terraform files already exist. Would you like to replace them? "
    #         "WARNING: This will overwrite any changes you have made to the terraform "
    #         "files."
    #     ):
    #         terraform_utils.populate_tf_definitions(provider, force=True)
    #     else:
    #         cli_utils.error(
    #             "Failed since the Terraform definition files already exist and you did not want to overwrite them."
    #         )

    # # warn that prerequisites should be met
    # metadata = terraform_utils.get_recipe_metadata(provider)
    # if not cli_utils.confirmation(
    #     "\nPrerequisites for running this recipe are as follows.\n"
    #     f"{metadata['Prerequisites']}"
    #     "\n\n Are all of these conditions met?"
    # ):
    #     cli_utils.error(
    #         "Prerequisites are not installed. Please make sure "
    #         "they are met and run deploy again."
    #     )

    # stack_recipe_name = f"{provider}_modular"

    # # create a directory for the stack recipe
    # unique_dir_name = cli_utils.generate_unique_recipe_directory_name(
    #     stack_recipe_name
    # )
    # temp_spec_dir = cli_utils.create_temp_spec_dir(unique_dir_name)

    # # convert json-formatted string to dict
    # if tags:
    #     import json

    #     tags = json.loads(tags)

    # stack_spec_config = MlstacksSpec(
    #     provider=provider,
    #     stack_name=stack_name,
    #     import_stack_flag=import_stack_flag,
    #     region=region,
    #     mlops_platform=mlops_platform,
    #     artifact_store=artifact_store,
    #     orchestrator=orchestrator,
    #     container_registry=container_registry,
    #     model_deployer=model_deployer,
    #     experiment_tracker=experiment_tracker,
    #     secrets_manager=secrets_manager,
    #     step_operator=step_operator,
    #     tags=tags,
    # )
    # cli_utils.generate_and_copy_spec_files(temp_spec_dir, stack_spec_config)

    # terraform_utils.deploy_stack(os.path.join(temp_spec_dir, "stack.yaml"))

    # with event_handler(
    #     event=AnalyticsEvent.RUN_STACK_RECIPE,
    #     metadata={"stack_recipe_name": stack_recipe_name},
    #     v2=True,
    # ) as handler:
    #     # build a dict of all stack component options that have non-null values
    #     stack_component_options = {
    #         "artifact_store": artifact_store,
    #         "orchestrator": orchestrator,
    #         "container_registry": container_registry,
    #         "model_deployer": model_deployer,
    #         "experiment_tracker": experiment_tracker,
    #         "secrets_manager": secrets_manager,
    #         "step_operator": step_operator,
    #     }

    #     # filter out null values
    #     stack_component_options = {
    #         k: v for k, v in stack_component_options.items() if v is not None
    #     }

    #     handler.metadata.update(stack_component_options)

    #     import python_terraform
    #     import yaml

    #     # get input variables
    #     variables_dict: Dict[str, Any] = {}

    #     if config:
    #         if os.path.isfile(config):
    #             variables_dict = yaml_utils.read_yaml(config)
    #         else:
    #             variables_dict = yaml.safe_load(config)
    #         if not isinstance(variables_dict, dict):
    #             cli_utils.error(
    #                 "The configuration argument must be JSON/YAML content or "
    #                 "point to a valid configuration file."
    #             )

    #     enabled_services = [
    #         f"{name}_{value}"
    #         for name, value in stack_component_options.items()
    #         if name
    #         not in [
    #             "artifact_store",
    #             "container_registry",
    #             "secrets_manager",
    #         ]
    #     ]
    #     enabled_services = enabled_services + [
    #         f"{name}"
    #         for name, _ in stack_component_options.items()
    #         if name
    #         in [
    #             "artifact_store",
    #             "container_registry",
    #             "secrets_manager",
    #         ]
    #     ]

    #     try:
    #         stack_recipe = git_stack_recipes_handler.get_stack_recipes(
    #             stack_recipe_name
    #         )[0]
    #     except KeyError as e:
    #         cli_utils.error(str(e))
    #     else:
    #         from zenml.recipes import (
    #             StackRecipeService,
    #             StackRecipeServiceConfig,
    #         )

    #         # warn that prerequisites should be met
    #         metadata = stack_recipe.metadata
    #         if not cli_utils.confirmation(
    #             "\nPrerequisites for running this recipe are as follows.\n"
    #             f"{metadata['Prerequisites']}"
    #             "\n\n Are all of these conditions met?"
    #         ):
    #             cli_utils.error(
    #                 "Prerequisites are not installed. Please make sure "
    #                 "they are met and run deploy again."
    #             )

    #         local_recipe_dir = Path(os.getcwd()) / path / stack_recipe_name

    #         # create the stack recipe service.
    #         stack_recipe_service_config = StackRecipeServiceConfig(
    #             directory_path=str(local_recipe_dir),
    #             skip_pull=skip_pull,
    #             force=force,
    #             log_level=log_level,
    #             enabled_services=enabled_services,
    #             input_variables=variables_dict,
    #         )

    #         stack_recipe_service = StackRecipeService.get_service(
    #             str(local_recipe_dir)
    #         )

    #         if stack_recipe_service:
    #             cli_utils.declare(
    #                 "An existing deployment of the recipe found. "
    #                 f"with path {local_recipe_dir}. "
    #                 "Proceeding to update or create resources. "
    #             )
    #         else:
    #             stack_recipe_service = StackRecipeService(
    #                 config=stack_recipe_service_config,
    #                 stack_recipe_name=stack_recipe_name,
    #             )

    #         try:
    #             # start the service (the init and apply operation)
    #             stack_recipe_service.start()

    #         except RuntimeError as e:
    #             cli_utils.error(
    #                 f"Running recipe {stack_recipe_name} failed: {str(e)} "
    #                 "\nPlease look at the error message to figure out "
    #                 "why the command failed. If the error is due some wrong "
    #                 "configuration, please consider checking the locals.tf "
    #                 "file to verify if the inputs are correct. Most commonly, "
    #                 "the command can fail due to a timeout error. In that "
    #                 "case, please run zenml stack recipe deploy "
    #                 f"{stack_recipe_name} again."
    #             )
    #         except python_terraform.TerraformCommandError:
    #             cli_utils.error(
    #                 f"Running recipe {stack_recipe_name} failed."
    #                 "\nPlease look at the error message to figure out why the "
    #                 "command failed. If the error is due some wrong "
    #                 "configuration, please consider checking the locals.tf "
    #                 "file to verify if the inputs are correct. Most commonly, "
    #                 "the command can fail due to a timeout error. In that "
    #                 "case, please run zenml stack recipe deploy "
    #                 f"{stack_recipe_name} again."
    #             )
    #     # invoke server deploy
    #     if no_server:
    #         cli_utils.warning("The `--no-server` flag has been deprecated.")

    #     # get the stack yaml path
    #     stack_yaml_file = os.path.join(
    #         stack_recipe_service.config.directory_path,
    #         stack_recipe_service.stack_file_path[2:],
    #     )

    #     cli_utils.declare(
    #         "\nA stack configuration YAML file has been generated "
    #         f"as part of the deployment of the {stack_recipe_name} "
    #         f"recipe. Find it at {stack_yaml_file}."
    #     )

    #     if import_stack_flag:
    #         cli_utils.declare(
    #             "\nThe flag `--import` is set. Proceeding "
    #             "to import a new ZenML stack from the created "
    #             "resources."
    #         )
    #         import_stack_name = stack_name if stack_name else stack_recipe_name
    #         cli_utils.declare(
    #             "Importing a new stack with the name " f"{import_stack_name}."
    #         )

    #         # import deployed resources as ZenML stack
    #         ctx.invoke(
    #             import_stack,
    #             stack_name=import_stack_name,
    #             filename=stack_yaml_file,
    #             ignore_version_mismatch=True,
    #         )

    #         cli_utils.declare(
    #             "Please consider creating any secrets that your "
    #             "stack components like the metadata store might "
    #             "need. You can inspect the fields of a stack "
    #             "component by running a describe command on them."
    #         )
    #         cli_utils.declare(
    #             "\n Run 'terraform output' in the recipe's "
    #             f"directory at {stack_recipe_service.config.directory_path} "
    #             "to get a list of outputs. To now retrieve sensitive "
    #             f"outputs, for example, the metadata-db-password "
    #             "use the command 'terraform output metadata-db-password' "
    #             "to get the value in the command-line."
    #         )


@stack.command(
    help="Destroy stack components created previously with "
    "`zenml stack deploy`"
)
@click.argument("stack_name", required=True)
@click.option(
    "--provider",
    "-p",
    "provider",
    type=click.Choice(STACK_RECIPE_MODULAR_RECIPES),
    help="The cloud provider on which the stack is deployed.",
)
@click.option(
    "--debug",
    "-d",
    "debug_mode",
    is_flag=True,
    default=False,
    help="Whether to run Terraform in debug mode.",
)
def destroy(
    stack_name: str,
    provider: str,
    debug_mode: bool = False,
) -> None:
    """Destroy all resources previously created with `zenml stack deploy`."""
    verify_mlstacks_installation()
    from mlstacks.constants import MLSTACKS_PACKAGE_NAME

    # check the stack actually exists
    if not stack_exists(stack_name):
        cli_utils.error(
            f"Stack with name '{stack_name}' does not exist. Please check and "
            "try again."
        )
    spec_file_path: str = (
        f"{click.get_app_dir(MLSTACKS_PACKAGE_NAME)}/stack_specs/{stack_name}"
    )
    tf_definitions_path: str = f"{click.get_app_dir(MLSTACKS_PACKAGE_NAME)}/terraform/{provider}-modular"

    verify_spec_and_tf_files_exist(spec_file_path, tf_definitions_path)

    from mlstacks.utils import terraform_utils

    terraform_utils.destroy_stack(
        stack_path=spec_file_path, debug_mode=debug_mode
    )

    if cli_utils.confirmation(
        f"Would you like to recursively delete the associated ZenML "
        f"stack '{stack_name}'?\nThis will delete the stack and any "
        "underlying stack components."
    ):
        from zenml.client import Client

        c = Client()
        c.delete_stack(stack_name=stack_name, recursive=True)
    if cli_utils.confirmation(
        f"Would you like to delete the `mlstacks` spec file for this stack, "
        f"located at {spec_file_path}?"
    ):
        remove(spec_file_path)
    cli_utils.declare(f"Stack '{stack_name}' successfully destroyed.")


# @stack_recipe.command(
#     help="Destroy the stack components created previously with "
#     "`zenml stack recipe deploy <name>`"
# )
# @click.argument("stack_recipe_name", required=True)
# @click.option(
#     "--path",
#     "-p",
#     type=click.STRING,
#     default="zenml_stack_recipes",
#     help="Relative path at which you want to install the stack_recipe(s)",
# )
# @click.option(
#     "--artifact-store",
#     "-a",
#     help="The flavor of artifact store to destroy. "
#     "If not specified, the default artifact store will be assumed.",
# )
# @click.option(
#     "--orchestrator",
#     "-o",
#     help="The flavor of orchestrator to destroy. "
#     "If not specified, the default orchestrator will be used.",
# )
# @click.option(
#     "--container-registry",
#     "-c",
#     help="The flavor of container registry to destroy. "
#     "If not specified, no container registry will be destroyed.",
# )
# @click.option(
#     "--model-deployer",
#     "-d",
#     help="The flavor of model deployer to destroy. "
#     "If not specified, no model deployer will be destroyed.",
# )
# @click.option(
#     "--experiment-tracker",
#     "-e",
#     help="The flavor of experiment tracker to destroy. "
#     "If not specified, no experiment tracker will be destroyed.",
# )
# @click.option(
#     "--step-operator",
#     "-s",
#     help="The flavor of step operator to destroy. "
#     "If not specified, no step operator will be destroyed.",
# )
# @pass_git_stack_recipes_handler
# def destroy(
#     git_stack_recipes_handler: GitStackRecipesHandler,
#     stack_recipe_name: str,
#     path: str,
#     artifact_store: Optional[str],
#     orchestrator: Optional[str],
#     container_registry: Optional[str],
#     model_deployer: Optional[str],
#     experiment_tracker: Optional[str],
#     step_operator: Optional[str],
# ) -> None:
#     """Destroy all resources from the stack_recipe at the specified relative path.

#     `zenml stack_recipe deploy stack_recipe_name` has to be called with the
#     same relative path before the destroy command. If you want to destroy
#     specific components of the stack, you can specify the component names
#     with the corresponding options. If no component is specified, all
#     components will be destroyed.

#     Args:
#         git_stack_recipes_handler: The GitStackRecipesHandler instance.
#         stack_recipe_name: The name of the stack_recipe.
#         path: The path of the stack recipe you want to destroy.
#         artifact_store: The flavor of the artifact store to destroy. In the case of
#             the artifact store, it doesn't matter what you specify here, as
#             there's only one flavor per cloud provider and that will be destroyed.
#         orchestrator: The flavor of the orchestrator to destroy.
#         container_registry: The flavor of the container registry to destroy. In the
#             case of the container registry, it doesn't matter what you specify
#             here, as there's only one flavor per cloud provider and that will be
#             destroyed.
#         model_deployer: The flavor of the model deployer to destroy.
#         experiment_tracker: The flavor of the experiment tracker to destroy.
#         step_operator: The flavor of the step operator to destroy.

#     Raises:
#         ModuleNotFoundError: If the recipe is found at the given path.
#     """
#     cli_utils.warning(ALPHA_MESSAGE)

#     with event_handler(
#         event=AnalyticsEvent.DESTROY_STACK_RECIPE,
#         metadata={"stack_recipe_name": stack_recipe_name},
#     ) as handler:
#         # build a dict of all stack component options that have non-null values
#         stack_component_options = {
#             "artifact_store": artifact_store,
#             "orchestrator": orchestrator,
#             "container_registry": container_registry,
#             "model_deployer": model_deployer,
#             "experiment_tracker": experiment_tracker,
#             "step_operator": step_operator,
#         }

#         # filter out null values
#         stack_component_options = {
#             k: v for k, v in stack_component_options.items() if v is not None
#         }

#         handler.metadata.update(stack_component_options)

#         # add all values that are not None to the disabled services list
#         disabled_services = [
#             f"{name}_{value}"
#             for name, value in stack_component_options.items()
#             if name
#             not in [
#                 "artifact_store",
#                 "container_registry",
#             ]
#         ]
#         # if artifact store, container registry or secrets manager
#         # are not none, add them as strings to the list of disabled services
#         disabled_services = disabled_services + [
#             f"{name}"
#             for name, _ in stack_component_options.items()
#             if name
#             in [
#                 "artifact_store",
#                 "container_registry",
#             ]
#         ]

#         try:
#             _ = git_stack_recipes_handler.get_stack_recipes(stack_recipe_name)[
#                 0
#             ]
#         except KeyError as e:
#             cli_utils.error(str(e))
#         else:
#             import python_terraform

#             from zenml.recipes import (
#                 StackRecipeService,
#             )

#             local_recipe_dir = Path(os.getcwd()) / path / stack_recipe_name

#             stack_recipe_service = StackRecipeService.get_service(
#                 str(local_recipe_dir)
#             )

#             if not stack_recipe_service:
#                 cli_utils.error(
#                     "No stack recipe found with the path "
#                     f"{local_recipe_dir}. You need to first deploy "
#                     "the recipe by running \nzenml stack recipe deploy "
#                     f"{stack_recipe_name}"
#                 )

#             if not stack_recipe_service.local_recipe_exists():
#                 raise ModuleNotFoundError(
#                     f"The recipe {stack_recipe_name} "
#                     "has not been pulled at the path  "
#                     f"{local_recipe_dir}. Please check  "
#                     "if you've deleted the recipe from the path."
#                 )

#             stack_recipe_service.config.disabled_services = disabled_services

#             try:
#                 # stop the service to destroy resources created by recipe
#                 stack_recipe_service.stop()
#             except python_terraform.TerraformCommandError as e:
#                 force_message = ""
#                 if stack_recipe_name == "aws_minimal":
#                     force_message = (
#                         "If there are Kubernetes resources that aren't"
#                         "getting deleted, run 'kubectl delete node -all' to "
#                         "delete the nodes and consequently all Kubernetes "
#                         "resources. Run the destroy again after that, to "
#                         "remove any other remaining resources."
#                     )
#                 cli_utils.error(
#                     f"Error destroying recipe {stack_recipe_name}: {str(e.err)}"
#                     "\nMost commonly, the error occurs if there's some "
#                     "resource that can't be deleted instantly, for example, "
#                     "MySQL stores with backups. In such cases, please try "
#                     "again after around 30 minutes. If the issue persists, "
#                     f"kindly raise an issue at {STACK_RECIPES_GITHUB_REPO}. "
#                     f"\n{force_message}"
#                 )
#             except subprocess.CalledProcessError as e:
#                 cli_utils.warning(
#                     f"Error destroying recipe {stack_recipe_name}: {str(e)}"
#                     "\nThe kubernetes cluster couldn't be removed due to the "
#                     "error above. Please verify if the cluster has already "
#                     "been deleted by running kubectl get nodes to check if "
#                     "there's any active nodes.Ignore this warning if there "
#                     "are no active nodes."
#                 )

#             cli_utils.declare(
#                 "\n" + "Your active stack might now be invalid. Please run:"
#             )
#             text = Text("zenml stack describe", style="markdown.code_block")
#             cli_utils.declare(text)
#             cli_utils.declare(
#                 "\n" + "to investigate and switch to a new stack if needed."
#             )


# a function to get the value of outputs passed as input, from a stack recipe
@stack_recipe.command(
    name="output",
    help="Get a specific output or a list of all outputs from a stack recipe.",
)
@click.argument("stack_recipe_name", type=str)
@click.option(
    "--path",
    "-p",
    type=click.STRING,
    default="zenml_stack_recipes",
    help="Relative path at which you want to install the stack_recipe(s)",
)
@click.option(
    "--output",
    "-o",
    type=click.STRING,
    default=None,
    help="Name of the output you want to get the value of. If none is given,"
    "all outputs are returned.",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["json", "yaml"], case_sensitive=False),
)
def get_outputs(
    stack_recipe_name: str,
    path: str,
    output: Optional[str],
    format: Optional[str],
) -> Union[Dict[str, Any], str]:
    """Get the outputs of the stack recipe at the specified relative path.

    `zenml stack_recipe deploy stack_recipe_name` has to be called from the
    same relative path before the get_outputs command.

    Args:
        git_stack_recipes_handler: The GitStackRecipesHandler instance.
        stack_recipe_name: The name of the stack_recipe.
        path: The path of the stack recipe you want to get the outputs from.
        output: The name of the output you want to get the value of. If none is given,
            all outputs are returned.
        format: The format of the output. If none is given, the output is printed
            to the console.

    Returns:
        One or more outputs of the stack recipe in the specified format.

    Raises:
        ModuleNotFoundError: If the recipe is found at the given path.
    """
    import json

    import yaml

    with event_handler(
        event=AnalyticsEvent.GET_STACK_RECIPE_OUTPUTS,
        metadata={"stack_recipe_name": stack_recipe_name},
    ):
        # import python_terraform

        # cli_utils.warning(ALPHA_MESSAGE)

        # stack_recipes_dir = Path(os.getcwd()) / path

        # try:
        #     _ = git_stack_recipes_handler.get_stack_recipes(stack_recipe_name)[
        #         0
        #     ]
        # except KeyError as e:
        #     cli_utils.error(str(e))
        # else:
        #     stack_recipe_dir = stack_recipes_dir / stack_recipe_name
        #     local_stack_recipe = LocalStackRecipe(
        #         stack_recipe_dir, stack_recipe_name
        #     )

        #     if not local_stack_recipe.is_present():
        #         raise ModuleNotFoundError(
        #             f"The recipe {stack_recipe_name} "
        #             "has not been pulled at the specified path. "
        #             f"Run `zenml stack recipe pull {stack_recipe_name}` "
        #             f"followed by `zenml stack recipe deploy "
        #             f"{stack_recipe_name}` first."
        #         )

        #     try:
        #         # use the stack recipe directory path to find the service instance
        #         from zenml.recipes import StackRecipeService

        #         stack_recipe_service = StackRecipeService.get_service(
        #             str(local_stack_recipe.path)
        #         )
        #         if not stack_recipe_service:
        #             cli_utils.error(
        #                 "No stack recipe found with the path "
        #                 f"{local_stack_recipe.path}. You need to first deploy "
        #                 "the recipe by running \nzenml stack recipe deploy "
        #                 f"{stack_recipe_name}"
        #             )
        outputs = cli_utils.get_recipe_outputs(stack_recipe_name, output)
        if output:
            if output in outputs:
                cli_utils.declare(f"Output {output}: ")
                return cast(Dict[str, Any], outputs[output])
            else:
                cli_utils.error(
                    f"Output {output} not found in stack recipe "
                    f"{stack_recipe_name}"
                )
        else:
            cli_utils.declare("Outputs: ")
            # delete all items that have empty values
            outputs = {k: v for k, v in outputs.items() if v != ""}

            if format == "json":
                outputs_json = json.dumps(outputs, indent=4)
                cli_utils.declare(outputs_json)
                return outputs_json
            elif format == "yaml":
                outputs_yaml = yaml.dump(outputs, indent=4)
                cli_utils.declare(outputs_yaml)
                return outputs_yaml
            else:
                cli_utils.declare(str(outputs))
                return outputs
            # except python_terraform.TerraformCommandError as e:
            #     cli_utils.error(str(e))
