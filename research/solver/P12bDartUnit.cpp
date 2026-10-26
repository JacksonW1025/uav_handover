// Real installed solver/world unit, not a flight or Gazebo/PX4 startup.
#include <dart/simulation/World.hpp>
#include <dart/dynamics/Skeleton.hpp>
#include <dart/dynamics/RevoluteJoint.hpp>
#include <dart/dynamics/BodyNode.hpp>
#include <dart/dynamics/Inertia.hpp>
#include <cstdio>
int main(){
 auto world=std::make_shared<dart::simulation::World>();world->setTimeStep(.004);world->setGravity(Eigen::Vector3d::Zero());
 auto body=dart::dynamics::Skeleton::create("p12b-unit");
 auto pair=body->createJointAndBodyNodePair<dart::dynamics::RevoluteJoint>();auto *j=pair.first;
 j->setName("rotor_unit_joint");j->setActuatorType(dart::dynamics::Joint::SERVO);
 dart::dynamics::Inertia inertia;inertia.setMass(1.0);inertia.setMoment(Eigen::Matrix3d::Identity());pair.second->setInertia(inertia);
 world->addSkeleton(body);
 for(int k=0;k<30;++k){j->setForceLowerLimit(0,k<10?-100.0:-.1);j->setForceUpperLimit(0,k<10?100.0:.1);j->setCommand(0,k<10?.1:10.0);world->step(false);std::printf("%d %.17g\n",k,j->getVelocity(0));}
 return 0;
}
